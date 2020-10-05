# Copyright 2020, Schuberg Philis B.V
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import socket
import time
from collections.abc import Mapping
from enum import Enum, auto
from operator import itemgetter

import click_spinner
import paramiko
from fabric import Connection

from .log import logging
from .vm import CosmicVM

FABRIC_PATCHED = False


class RebootAction(Enum):
    REBOOT = auto()
    HALT = auto()
    FORCE_RESET = auto()
    UPGRADE_FIRMWARE = auto()
    PXE_REBOOT = auto()
    SKIP = auto()


class CosmicHost(Mapping):
    def __init__(self, ops, host):
        global FABRIC_PATCHED
        self._ops = ops
        self._host = host
        self.log_to_slack = ops.log_to_slack
        self.dry_run = ops.dry_run

        # Patch Fabric connection to use different host policy (see https://github.com/fabric/fabric/issues/2071)
        def unsafe_open(self):
            self.client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
            Connection.open_orig(self)

        if not FABRIC_PATCHED:
            Connection.open_orig = Connection.open
            Connection.open = unsafe_open
            FABRIC_PATCHED = True

        # Setup our connection
        self._connection = Connection(self._host['name'])

        self.vms_with_shutdown_policy = []

    def __getitem__(self, item):
        return self._host[item]

    def __iter__(self):
        return iter(self._host)

    def __len__(self):
        return len(self._host)

    def refresh(self):
        self._host = self._ops.get_host_json_by_id(self['id'])[0]

    def disable(self):
        if self.dry_run:
            logging.info(f"Would disable host '{self['name']}'")
            return True
        else:
            logging.info(f"Disabling host '{self['name']}'", self.log_to_slack)

        if not self._ops.cs.updateHost(id=self['id'], allocationstate='Disable').get('host'):
            logging.error(f"Failed to disable host '{self['name']}'", self.log_to_slack)
            return False

        with click_spinner.spinner():
            while True:
                self.refresh()
                if self['resourcestate'] == 'Disabled':
                    break
                time.sleep(5)

        return True

    def enable(self):
        if self.dry_run:
            logging.info(f"Would enable host '{self['name']}'")
            return True
        else:
            logging.info(f"Enabling host '{self['name']}'", self.log_to_slack)

        if not self._ops.cs.updateHost(id=self['id'], allocationstate='Enable').get('host'):
            logging.error(f"Failed to enable host '{self['name']}'", self.log_to_slack)
            return False

        with click_spinner.spinner():
            while True:
                self.refresh()
                if self['resourcestate'] == 'Enabled':
                    break
                time.sleep(5)

        return True

    def empty(self):
        total = success = failed = 0

        all_vms = self.get_all_vms()
        if not all_vms:
            logging.warning(f"No VMs found on host '{self['name']}'")
            return total, success, failed

        total = len(all_vms)

        if self.dry_run:
            logging.info(f"Dry run of VM migration away from host '{self['name']}'")
        else:
            logging.info(f"Migrating VMs away from host '{self['name']}'")

        for vm in all_vms:
            if vm.get('maintenancepolicy') == 'ShutdownAndStart':
                # TODO: currently the VM remains stopped, would be nice to have it start again if possible.
                # * Do not try to start if the host is on NVMe
                # * If it's on shared storage it can be started on another host after this one has been disabled
                self.vms_with_shutdown_policy.append(vm)

                if not vm.stop():
                    failed += 1
                else:
                    success += 1

                continue

            vm_on_dedicated_hv = False
            dedicated_affinity_id = None
            for affinity_group in vm.get_affinity_groups():
                if affinity_group['type'] == 'ExplicitDedication':
                    vm_on_dedicated_hv = True
                    dedicated_affinity_id = affinity_group['id']

            available_hosts = self._ops.cs.findHostsForMigration(virtualmachineid=vm['id']).get('host', [])
            available_hosts.sort(key=itemgetter('memoryallocated'))
            migration_host = None

            for available_host in available_hosts:
                # Skip hosts that require storage migration
                if available_host['requiresStorageMotion']:
                    logging.debug(
                        f"Skipping '{available_host['name']}' because migrating VM '{vm['name']}' requires a storage migration")
                    continue

                # Only hosts in the same cluster
                if available_host['clusterid'] != self['clusterid']:
                    logging.debug(f"Skipping '{available_host['name']}' because it's part of a different cluster")
                    continue

                # Ensure host is suitable for migration
                if not available_host['suitableformigration']:
                    logging.debug(f"Skipping '{available_host['name']}' because it's not suitable for migration")
                    continue

                if vm_on_dedicated_hv:
                    # Ensure the dedication group matches
                    if available_host.get('affinitygroupid') != dedicated_affinity_id:
                        logging.info(
                            f"Skipping '{available_host['name']}' because host does not match the dedication group of VM '{vm['name']}'")
                        continue
                else:
                    # VM isn't dedicated, so skip dedicated hosts
                    if 'affinitygroupid' in available_host:
                        logging.info(
                            f"Skipping '{available_host['name']}' because host is dedicated and VM '{vm['name']}' is not")
                        continue

                logging.debug(f"Selected '{available_host['name']}' for VM '{vm['name']}'")
                migration_host = available_host
                break

            if not migration_host:
                logging.error(
                    f"Failed to find host with capacity to migrate VM '{vm['name']}'. Please migrate manually to another cluster.")
                failed += 1
                continue

            if not vm.migrate(migration_host):
                failed += 1
            else:
                success += 1

        return total, success, failed

    def get_all_vms(self):
        vms = self._ops.cs.listVirtualMachines(hostid=self['id'], listall='true').get('virtualmachine', [])
        project_vms = self._ops.cs.listVirtualMachines(hostid=self['id'], listall='true', projectid='-1').get(
            'virtualmachine', [])
        routers = self._ops.cs.listRouters(hostid=self['id'], listall='true').get('router', [])
        project_routers = self._ops.cs.listRouters(hostid=self['id'], listall='true', projectid='-1').get('router', [])
        system_vms = self._ops.cs.listSystemVms(hostid=self['id']).get('systemvm', [])

        all_vms = vms + project_vms + routers + project_routers + system_vms
        return [CosmicVM(self._ops, vm) for vm in all_vms]

    def copy_file(self, source, destination, mode=None):
        if self.dry_run:
            logging.info(f"Would copy '{source}' to '{destination}' on '{self['name']}")
            return

        self._connection.put(source, destination)
        if mode:
            self._connection.sudo(f'chmod {mode:o} {destination}')

    def execute(self, command, sudo=False):
        if self.dry_run:
            logging.info(f"Would execute '{command}' on '{self['name']}")
            return

        if sudo:
            runner = self._connection.sudo
        else:
            runner = self._connection.run

        return runner(command)

    def reboot(self, action=RebootAction.REBOOT):
        if self.dry_run:
            logging.info(f"Would reboot host '{self['name']}' with action '{action}'")
            return True

        if self.execute('virsh list | grep running | wc -l').stdout.strip() != '0':
            logging.error(f"Host '{self['name']}' has running VMs, will not reboot", self.log_to_slack)
            return False

        try:
            if action == RebootAction.REBOOT:
                logging.info(f"Rebooting '{self['name']}' in 60s", self.log_to_slack)
                self.execute('shutdown -r 1', sudo=True)
            elif action == RebootAction.HALT:
                logging.info(
                    f"Halting '{self['name']}' in 60s, be sure to start it manually to continue the rolling reboot",
                    self.log_to_slack)
                self.execute('shutdown -h 1', sudo=True)
            elif action == RebootAction.FORCE_RESET:
                logging.info(f"Force resetting '{self['name']}'", self.log_to_slack)
                self.execute('sync', sudo=True)
                self.execute('echo b > /proc/sysrq-trigger', sudo=True)
            elif action == RebootAction.UPGRADE_FIRMWARE:
                logging.info(f"Rebooting '{self['name']}' after firmware upgrade", self.log_to_slack)
                self.execute("tmux new -d 'yes | sudo /usr/sbin/smartupdate upgrade && sudo reboot'")
            elif action == RebootAction.PXE_REBOOT:
                logging.info(f"PXE Rebooting '{self['name']}' in 10s", self.log_to_slack)
                self.execute("tmux new -d 'sleep 10 && sudo /usr/sbin/hp-reboot pxe'")
            elif action == RebootAction.SKIP:
                logging.info(f"Skipping reboot for '{self['name']}'", self.log_to_slack)
        except Exception as e:
            logging.warning(f"Ignoring exception as it's likely related to the reboot: {e}", self.log_to_slack)

        return True

    def wait_until_offline(self):
        if self.dry_run:
            logging.info(f"Would wait for '{self['name']}' to complete it's reboot")
        else:
            logging.info(f"Waiting for '{self['name']}' to complete it's reboot", self.log_to_slack)
            with click_spinner.spinner():
                while True:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(5)
                        result = s.connect_ex((self['name'], 22))

                    if result != 0:
                        break
                    time.sleep(5)

    def wait_until_online(self):
        if self.dry_run:
            logging.info(f"Would wait for '{self['name']}' to come back online")
        else:
            logging.info(f"Waiting for '{self['name']}' to come back online", self.log_to_slack)
            with click_spinner.spinner():
                while True:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(5)
                        result = s.connect_ex((self['name'], 22))

                    if result == 0:
                        break

        if self.dry_run:
            logging.info(f"Would wait for libvirt on '{self['name']}'")
        else:
            logging.info(f"Waiting for libvirt on '{self['name']}'", self.log_to_slack)
            with click_spinner.spinner():
                while True:
                    try:
                        if self.execute('virsh list').return_code == 0:
                            break
                    except ConnectionResetError:
                        pass

                    time.sleep(5)

    def restart_vms_with_shutdown_policy(self):
        if self.dry_run:
            logging.info(f"Would restart VMs with 'ShutdownAndStart' policy on host '{self['name']}'")
        else:
            logging.info(f"Starting VMs with 'ShutdownAndStart' policy on host '{self['name']}'", self.log_to_slack)

        for vm in self.vms_with_shutdown_policy:
            vm.start()

    def wait_for_agent(self):
        if self.dry_run:
            logging.info(f"Would wait for agent to became up on host '{self['name']}'")
            return
        else:
            logging.info(f"Waiting for agent on host '{self['name']}'", self.log_to_slack)

        with click_spinner.spinner():
            while True:
                self.refresh()
                if self['state'] == 'Up':
                    break

                time.sleep(5)

    def __del__(self):
        if self._connection:
            self._connection.close()

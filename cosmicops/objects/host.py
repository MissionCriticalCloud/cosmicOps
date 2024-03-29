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
from datetime import datetime
from dataclasses import dataclass
from enum import Enum, auto
from operator import itemgetter
from xml.etree import ElementTree

import click_spinner
import hpilo
import libvirt
import paramiko
from cs import CloudStackApiException
from fabric import Connection
from invoke import UnexpectedExit, CommandTimedOut

from cosmicops import get_config, logging
from .object import CosmicObject
from .router import CosmicRouter
from .vm import CosmicVM

FABRIC_PATCHED = False


class RebootAction(Enum):
    REBOOT = auto()
    HALT = auto()
    FORCE_RESET = auto()
    UPGRADE_FIRMWARE = auto()
    PXE_REBOOT = auto()
    SKIP = auto()


@dataclass(frozen=True, order=True)
class DomJobInfo:
    jobType: int = libvirt.VIR_DOMAIN_JOB_NONE
    operation: int = 0
    timeElapsed: int = 0
    timeRemaining: int = 0
    dataTotal: int = 0
    dataProcessed: int = 0
    dataRemaining: int = 0
    memTotal: int = 0
    memProcessed: int = 0
    memRemaining: int = 0
    fileTotal: int = 0
    fileProcessed: int = 0
    fileRemaing: int = 0

    @classmethod
    def from_list(cls, l: list):
        return cls(*l)


@dataclass(frozen=True, order=True)
class BlkJobInfo:
    jobType: int = 0
    bandWidth: int = 0
    current: int = 0
    end: int = 0


# Patch Fabric connection to use different host policy (see https://github.com/fabric/fabric/issues/2071)
def unsafe_open(self):  # pragma: no cover
    self.client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
    Connection.open_orig(self)


class CosmicHost(CosmicObject):
    def __init__(self, ops, data):
        super().__init__(ops, data)
        global FABRIC_PATCHED

        if not FABRIC_PATCHED:
            Connection.open_orig = Connection.open
            Connection.open = unsafe_open
            FABRIC_PATCHED = True

        # Load configuration
        config = get_config()
        ssh_user = config.get('ssh', 'user', fallback=None)
        ssh_key_file = config.get('ssh', 'ssh_key_file', fallback=None)
        connect_kwargs = {'key_filename': ssh_key_file} if ssh_key_file else None

        ilo_user = config.get('ilo', 'user', fallback=None)
        ilo_password = config.get('ilo', 'password', fallback=None)

        # Setup SSH connection
        self._connection = Connection(self['name'], user=ssh_user, connect_kwargs=connect_kwargs)

        # Setup ILO connection
        ilo_address = self['name'].split('.')
        ilo_address.insert(1, 'ilom')
        ilo_address = '.'.join(ilo_address)
        self._ilo = hpilo.Ilo(ilo_address, login=ilo_user, password=ilo_password)

        self.vms_with_shutdown_policy = []

    def refresh(self):
        self._data = self._ops.get_host(id=self['id'], json=True)

    def update_tags(self, hosttags="", add=True):
        changed = False
        current_tags = self['hosttags'].split(',') if 'hosttags' in self else []
        tags = {x: x for x in current_tags}

        for h in hosttags:
            if add and h not in current_tags:
                tags[h] = h
                changed = True
            elif not add and h in current_tags:
                tags.pop(h)
                changed = True

        if changed:
            tags = ','.join([x for x in tags])
            if not tags:
                tags = " "

            t = 'adding' if add else 'deleting'
            if self.dry_run:
                logging.info(f"Would update host '{self['name']}', {t} tags '{hosttags}'")
                return True
            else:
                logging.info(f"Updating host '{self['name']}', {t} tags '{hosttags}'")
                if not self._ops.cs.updateHost(id=self['id'], hosttags=tags).get('host'):
                    logging.error(f"Failed to update tags on host '{self['name']}'")
                    return False
        else:
            logging.info(f"Nothing to update on host '{self['name']}'")
        return True

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

    def empty(self, target=None):
        total = success = failed = 0
        logging.cluster = self['name']
        logging.zone_name = self['zonename']

        all_vms = self.get_all_vms() + self.get_all_project_vms() + self.get_all_routers() + self.get_all_project_routers() + self.get_all_system_vms()
        if not all_vms:
            logging.warning(f"No VMs found on host '{self['name']}'")
            return total, success, failed

        total = len(all_vms)

        target_message = f" to target '{target['name']}'" if target else ''
        if self.dry_run:
            logging.info(f"Dry run of VM migration away from host '{self['name']}'" + target_message)
        else:
            logging.info(f"Migrating VMs away from host '{self['name']}'" + target_message)

        for vm in all_vms:
            logging.instance_name = vm.get('name', 'N/A')
            logging.vm_name = vm.get('instancename', 'N/A')
            logging.slack_value = vm.get('domain', 'N/A')

            if vm.get('maintenancepolicy') == 'ShutdownAndStart':
                if not vm.stop():
                    failed += 1
                    continue

                success += 1

                # If the host is disabled, try to restart the VM. Will fail if the host is on NVMe.
                if self['resourcestate'] == 'Disabled':
                    if vm.start(host=target):
                        continue

                self.vms_with_shutdown_policy.append(vm)
                continue

            vm_on_dedicated_hv = False
            dedicated_affinity_id = None
            for affinity_group in vm.get_affinity_groups():
                if affinity_group['type'] == 'ExplicitDedication':
                    vm_on_dedicated_hv = True
                    dedicated_affinity_id = affinity_group['id']

            if target:
                available_hosts = [target]
            else:
                try:
                    available_hosts = self._ops.cs.findHostsForMigration(virtualmachineid=vm['id']).get('host', [])
                except CloudStackApiException as e:
                    logging.error(f"Encountered API exception while finding suitable host for migration: {e}")
                    failed += 1
                    continue
                available_hosts.sort(key=itemgetter('memoryallocated'))

            migration_host = None

            for available_host in available_hosts:
                if not target:
                    # Skip hosts that require storage migration
                    if available_host['requiresStorageMotion']:
                        logging.debug(
                            f"Skipping '{available_host['name']}' because migrating VM '{vm['name']}' requires a storage migration")
                        continue

                    # Ensure host is suitable for migration
                    if not available_host['suitableformigration']:
                        logging.debug(f"Skipping '{available_host['name']}' because it's not suitable for migration")
                        continue

                # Only hosts in the same cluster
                if available_host['clusterid'] != self['clusterid']:
                    logging.debug(f"Skipping '{available_host['name']}' because it's part of a different cluster")
                    continue

                if vm_on_dedicated_hv:
                    # Ensure the dedication group matches
                    if available_host.get('affinitygroupid') != dedicated_affinity_id:
                        logging.info(
                            f"Skipping '{available_host['name']}' because host does not match the dedication group of VM '{vm['name']}'")
                        continue
                else:
                    # If the user VM isn't dedicated, skip dedicated hosts
                    if vm.is_user_vm() and 'affinitygroupid' in available_host:
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

    def get_all_vms(self, domain=None, keyword_filter=None):
        domain_id = domain['id'] if domain else None

        vms = self._ops.cs.listVirtualMachines(fetch_list=True, hostid=self['id'], domainid=domain_id,
                                               keyword=keyword_filter, listall='true')

        return [CosmicVM(self._ops, vm) for vm in vms]

    def get_all_project_vms(self, project=None):
        if project:
            project_id = project['id']
        else:
            project_id = '-1'

        project_vms = self._ops.cs.listVirtualMachines(fetch_list=True, hostid=self['id'], listall='true',
                                                       projectid=project_id)

        return [CosmicVM(self._ops, vm) for vm in project_vms]

    def get_all_routers(self, domain=None):
        domain_id = domain['id'] if domain else None

        routers = self._ops.cs.listRouters(fetch_list=True, hostid=self['id'], domainid=domain_id, listall='true')

        return [CosmicRouter(self._ops, router) for router in routers]

    def get_all_project_routers(self, project=None):
        if project:
            project_id = project['id']
        else:
            project_id = '-1'

        project_routers = self._ops.cs.listRouters(fetch_list=True, hostid=self['id'], listall='true',
                                                   projectid=project_id)

        return [CosmicRouter(self._ops, router) for router in project_routers]

    def get_all_system_vms(self):
        system_vms = self._ops.cs.listSystemVms(fetch_list=True, hostid=self['id'])

        return [CosmicVM(self._ops, vm) for vm in system_vms]

    def copy_file(self, source, destination, mode=None):
        if self.dry_run:
            logging.info(f"Would copy '{source}' to '{destination}' on '{self['name']}")
            return

        self._connection.put(source, destination)
        if mode:
            self._connection.sudo(f'chmod {mode:o} {destination}')

    def execute(self, command, sudo=False, hide_stdout=True, pty=False, always=False):
        if self.dry_run and not always:
            logging.info(f"Would execute '{command}' on '{self['name']}")
            return

        logging.info(f"Executing '{command}' on '{self['name']}")

        if sudo:
            runner = self._connection.sudo
        else:
            runner = self._connection.run

        return runner(command, hide=hide_stdout, pty=pty)

    def reboot(self, action=RebootAction.REBOOT):
        reboot_or_halt = 'halt' if action == RebootAction.HALT else 'reboot'

        if self.dry_run:
            logging.info(f"Would {reboot_or_halt} host '{self['name']}' with action '{action}'")
            return True

        if self.execute('virsh list | grep running | wc -l').stdout.strip() != '0':
            logging.error(f"Host '{self['name']}' has running VMs, will not {reboot_or_halt}", self.log_to_slack)
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
                self.execute("tmux new -d 'yes | sudo /usr/sbin/smartupdate upgrade && sudo reboot'", pty=True)
            elif action == RebootAction.PXE_REBOOT:
                logging.info(f"PXE Rebooting '{self['name']}' in 10s", self.log_to_slack)
                self.execute("tmux new -d 'sleep 10 && sudo /usr/sbin/hp-reboot pxe'", pty=True)
            elif action == RebootAction.SKIP:
                logging.info(f"Skipping reboot for '{self['name']}'", self.log_to_slack)
        except Exception as e:
            logging.warning(f"Ignoring exception as it's likely related to the {reboot_or_halt}: {e}",
                            self.log_to_slack)

        return True

    def set_uid_led(self, state):
        new_state = 'on' if state else 'off'
        if self.dry_run:
            logging.info(f"Would set UID led {new_state}")
        else:
            self.execute(f'hpasmcli -s "set uid {new_state}"', sudo=True)

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
            # adding retry tests, so we need to be able to connect to SSH three times in one minute
            # before we consider the host up
            tests = 1
            while tests <= 3:
                logging.info(f"Waiting for SSH connection, attempt {tests} of 3", False)
                with click_spinner.spinner():
                    while True:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.settimeout(5)
                            try:
                                result = s.connect_ex((self['name'], 22))
                            except Exception as e:
                                logging.warning(f'Connection failed due to {e}')
                                result = 1

                        if result == 0:
                            break
                    time.sleep(20)
                tests += 1

        if self.dry_run:
            logging.info(f"Would wait for libvirt on '{self['name']}'")
        else:
            logging.info(f"Waiting for libvirt on '{self['name']}'", self.log_to_slack)
            with click_spinner.spinner():
                while True:
                    try:
                        if self.execute('virsh list').return_code == 0:
                            break
                    except (ConnectionResetError, UnexpectedExit, CommandTimedOut):
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

    def get_disks(self, vm_instancename):
        lv = libvirt.openReadOnly(f"qemu+tcp://{self['name']}/system")

        domain = lv.lookupByName(vm_instancename)

        tree = ElementTree.fromstring(domain.XMLDesc())
        block_devs = tree.findall('devices/disk')

        disk_data = {}

        for disk in block_devs:
            if disk.get('device') != 'disk':
                continue

            dev = disk.find('target').get('dev')
            full_path = disk.find('source').get('file')
            if full_path is None:
                logging.info(f"Skipping disk without a file (NVMe?)")
                continue
            _, _, pool, path = full_path.split('/')

            size, _, _ = domain.blockInfo(dev)

            disk_data[path] = {
                'dev': dev,
                'pool': pool,
                'path': path,
                'size': size
            }

        lv.close()

        return disk_data

    def get_domjobinfo(self, vm_instancename):
        try:
            lv = libvirt.openReadOnly(f"qemu+tcp://{self['name']}/system")
            all_domains = lv.listAllDomains()
            if any([x for x in all_domains if x.name() == vm_instancename]):
                domain = lv.lookupByName(vm_instancename)
                domjobinfo = domain.jobInfo()
                return DomJobInfo.from_list(domjobinfo)
        except libvirt.libvirtError as _:
            pass  # Ignore exception
        return DomJobInfo()

    def get_domjobstats(self, vm_instancename, correction=True):
        try:
            lv = libvirt.openReadOnly(f"qemu+tcp://{self['name']}/system")
            all_domains = lv.listAllDomains()
            if any([x for x in all_domains if x.name() == vm_instancename]):
                domain = lv.lookupByName(vm_instancename)
                domjobstats = domain.jobStats()
                memory_total = domjobstats.get('memory_total', 0)
                if correction:
                    if memory_total == 0:
                        c_add = domain.info()[0]
                        memory_total = memory_total + c_add
                return DomJobInfo(
                    jobType=domjobstats.get('type', libvirt.VIR_DOMAIN_JOB_NONE),
                    operation=domjobstats.get('operation', 0),
                    timeElapsed=domjobstats.get('time_elapsed', 0),
                    timeRemaining=domjobstats.get('time_remaining', 0),
                    dataTotal=domjobstats.get('data_total', 0),
                    dataProcessed=domjobstats.get('data_processed', 0),
                    dataRemaining=domjobstats.get('data_remaining', 0),
                    memTotal=memory_total,
                    memProcessed=domjobstats.get('memory_processed', 0),
                    memRemaining=domjobstats.get('memory_remaining', 0),
                    fileTotal=domjobstats.get('disk_total', 0),
                    fileProcessed=domjobstats.get('disk_processed', 0),
                    fileRemaing=domjobstats.get('disk_remaining', 0)
                )
        except libvirt.libvirtError as _:
            pass  # Ignore exception
        return DomJobInfo()

    def get_blkjobinfo(self, vm_instancename, volume):
        try:
            disks = self.get_disks(vm_instancename)
            disk = dict(filter(lambda x: x[0] == volume, disks.items()))
            lv = libvirt.openReadOnly(f"qemu+tcp://{self['name']}/system")
            all_domains = lv.listAllDomains()
            if any([x for x in all_domains if x.name() == vm_instancename]):
                domain = lv.lookupByName(vm_instancename)
                blkjobinfo = domain.blockJobInfo(disk[volume]['dev'], 0)
                return BlkJobInfo(
                    jobType=blkjobinfo.get('type', 0),
                    bandWidth=blkjobinfo.get('bandwidth', 0),
                    current=blkjobinfo.get('cur', 0),
                    end=blkjobinfo.get('end', 0)
                )
        except libvirt.libvirtError as _:
            pass  # Ignore exception
        return BlkJobInfo()

    def set_iops_limit(self, vm_instancename, max_iops):
        command = f"""
        for i in $(/usr/bin/virsh domblklist --details '{vm_instancename}' | grep disk | grep file | /usr/bin/awk '{{print $3}}'); do
            /usr/bin/virsh blkdeviotune '{vm_instancename}' $i --total-iops-sec {max_iops} --live
        done
        """

        if not self.execute(command, sudo=True).return_code == 0:
            logging.error(f"Failed to set IOPS limit for '{vm_instancename}'")
            return False
        else:
            return True

    def merge_backing_files(self, vm_instancename):
        command = f"""
        for i in $(/usr/bin/virsh domblklist --details '{vm_instancename}' | grep disk | grep file | /usr/bin/awk '{{print $3}}'); do
            /usr/bin/virsh blockpull '{vm_instancename}' $i --wait --verbose
        done
        """
        if not self.execute(command, sudo=True).return_code == 0:
            logging.error(f"Failed to merge backing volumes for '{vm_instancename}'")
            return False
        else:
            return True

    def power_on(self):
        try:
            self._ilo.set_host_power(True)
            return True
        except Exception as err:
            logging.error(f"Failed to power on '{self['name']}': {err}")
            return False

    def file_exists(self, path):
        try:
            result = self.execute(f"/bin/ls -la \"{path}\"", always=True).stdout
            return result.split()
        except UnexpectedExit:
            return []

    def rename_file(self, source, destination):
        try:
            if not self.execute(f"/bin/mv \"{source}\" \"{destination}\"", True).return_code == 0:
                return False

            return True
        except UnexpectedExit:
            return False

    def rename_existing_destination_file(self, path):
        timestamp = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        magweg = f"magweg-migration-{timestamp}"
        logging.info(f"Renaming {path} to {path}.{magweg} on host {self['name']}")
        if not self.rename_file(path, f"{path}.{magweg}"):
            return False

        return True

    def __del__(self):
        if self._connection:
            self._connection.close()

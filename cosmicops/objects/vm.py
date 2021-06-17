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
from operator import itemgetter

from cs import CloudStackException, CloudStackApiException

from cosmicops.log import logging
from .object import CosmicObject
from .volume import CosmicVolume


class CosmicVM(CosmicObject):
    def refresh(self):
        self._data = self._ops.get_vm(id=self['id'], json=True)

    def stop(self):
        if self.dry_run:
            logging.info(f"Would stop VM '{self['name']} on host '{self['hostname']}'")
            return True

        if self.get('maintenancepolicy') == 'ShutdownAndStart':
            logging.info(
                f"Stopping VM '{self['name']}' on host '{self['hostname']}' as it has a ShutdownAndStart policy",
                self.log_to_slack)
        else:
            logging.info(f"Stopping VM '{self['name']}' on host '{self['hostname']}'", self.log_to_slack)
        stop_response = self._ops.cs.stopVirtualMachine(id=self['id'])
        if not self._ops.wait_for_job(stop_response['jobid']):
            logging.error(f"Failed to shutdown VM '{self['name']}' on host '{self['hostname']}'")
            return False

        return True

    def start(self, host=None):
        if host:
            host_id = host['id']
            on_host_msg = f" on host '{host['name']}'"
        else:
            host_id = None
            on_host_msg = ''

        if self.dry_run:
            logging.info(f"Would start VM '{self['name']}{on_host_msg}")
            return True

        logging.info(f"Starting VM '{self['name']}'{on_host_msg}'", self.log_to_slack)
        start_response = self._ops.cs.startVirtualMachine(id=self['id'], hostid=host_id)
        if not self._ops.wait_for_job(start_response['jobid']):
            logging.error(f"Failed to start VM '{self['name']}'")
            return False

        return True

    def get_affinity_groups(self):
        affinity_groups = []
        try:
            affinity_groups = self._ops.cs.listAffinityGroups(fetch_list=True, virtualmachineid=self['id'])
        except CloudStackException:
            pass

        return affinity_groups

    def get_snapshots(self):
        vm_snapshots = []
        try:
            if 'projectid' in self:
                vm_snapshots = self._ops.cs.listVMSnapshot(fetch_list=True, virtualmachineid=self['id'], listall='true',
                                                           projectid=-1)
            else:
                vm_snapshots = self._ops.cs.listVMSnapshot(fetch_list=True, virtualmachineid=self['id'], listall='true')

        except CloudStackException as e:
            logging.error(f'Exception {str(e)}')

        return vm_snapshots

    def get_volumes(self):
        if 'projectid' in self:
            volumes = self._ops.cs.listVolumes(fetch_list=True, virtualmachineid=self['id'], listall='true',
                                               projectid=-1)
        else:
            volumes = self._ops.cs.listVolumes(fetch_list=True, virtualmachineid=self['id'], listall='true')

        return [CosmicVolume(self._ops, volume) for volume in volumes]

    def detach_iso(self):
        if 'isoid' in self:
            self._ops.cs.detachIso(virtualmachineid=self['id'])

    def is_user_vm(self):
        return True if 'instancename' in self else False

    def migrate_within_cluster(self, vm, source_cluster, **kwargs):
        logging.instance_name = vm['instancename']
        logging.slack_value = vm['domain']
        logging.vm_name = vm['name']
        logging.zone_name = vm['zonename']
        logging.cluster = source_cluster['name']

        try:
            available_hosts = self._ops.cs.findHostsForMigration(virtualmachineid=vm['id']).get('host', [])
        except CloudStackApiException as e:
            logging.error(f"Encountered API exception while finding suitable host for migration: {e}")
            return False
        available_hosts.sort(key=itemgetter('memoryallocated'))

        migration_host = None

        for available_host in available_hosts:
            # Only hosts in the same cluster
            if available_host['clusterid'] != source_cluster['id']:
                logging.debug(f"Skipping '{available_host['name']}' because it's not part of the current cluster")
                continue
            migration_host = available_host
            break
        if migration_host is None:
            return False

        return self.migrate(target_host=migration_host, **kwargs)

    def migrate(self, target_host, with_volume=False, **kwargs):
        if self.dry_run:
            logging.info(f"Would live migrate VM '{self['name']}' to '{target_host['name']}'")
            return True

        if with_volume:
            migrate_func = self._ops.cs.migrateVirtualMachineWithVolume
        else:
            migrate_func = self._ops.cs.migrateVirtualMachine

        try:
            logging.info(f"Live migrating VM '{self['name']}' to '{target_host['name']}'", self.log_to_slack)

            if self.is_user_vm():
                self.detach_iso()

                vm_result = migrate_func(virtualmachineid=self['id'], hostid=target_host['id'])
                if not vm_result:
                    raise RuntimeError
            else:
                vm_result = self._ops.cs.migrateSystemVm(virtualmachineid=self['id'], hostid=target_host['id'])
                if not vm_result:
                    raise RuntimeError
        except (CloudStackException, RuntimeError):
            logging.error(f"Failed to migrate VM '{self['name']}'")
            return False

        job_id = vm_result['jobid']
        if not self._ops.wait_for_vm_migration_job(job_id, **kwargs):
            logging.error(f"Migration job '{vm_result['jobid']}' failed")
            return False

        logging.debug(f"Migration job '{vm_result['jobid']}' completed")

        logging.debug(f"Successfully migrated VM '{self['name']}' to '{target_host['name']}'")
        return True

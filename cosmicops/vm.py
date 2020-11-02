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

from cs import CloudStackException

from .log import logging
from .object import CosmicObject


class CosmicVM(CosmicObject):
    def __init__(self, ops, data):
        super().__init__(ops, data)
        self.log_to_slack = ops.log_to_slack

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

    def start(self):
        if self.dry_run:
            logging.info(f"Would start VM '{self['name']} on host '{self['hostname']}'")
            return True

        logging.info(f"Starting VM '{self['name']}' on host '{self['hostname']}'", self.log_to_slack)
        start_response = self._ops.cs.startVirtualMachine(id=self['id'])
        if not self._ops.wait_for_job(start_response['jobid']):
            logging.error(f"Failed to start VM '{self['name']}'")
            return False

        return True

    def get_affinity_groups(self):
        affinity_groups = []
        try:
            affinity_groups = self._ops.cs.listAffinityGroups(virtualmachineid=self['id']).get('affinitygroup', [])
        except CloudStackException:
            pass

        return affinity_groups

    def get_volumes(self):
        return self._ops.cs.listVolumes(virtualmachineid=self['id'], listall='true').get('volume', [])

    def migrate(self, target_host):
        if self.dry_run:
            logging.info(f"Would live migrate VM '{self['name']}' to '{target_host['name']}'")
            return True

        try:
            logging.info(f"Live migrating VM '{self['name']}' to '{target_host['name']}'", self.log_to_slack)

            if 'instancename' in self:
                if 'isoid' in self:
                    self._ops.cs.detachIso(virtualmachineid=self['id'])

                vm_result = self._ops.cs.migrateVirtualMachine(virtualmachineid=self['id'],
                                                               hostid=target_host['id'])
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
        if not self._ops.wait_for_job(job_id):
            logging.error(f"Migration job '{vm_result['jobid']}' failed")
            return False

        logging.debug(f"Migration job '{vm_result['jobid']}' completed")

        logging.debug(f"Successfully migrated VM '{self['name']}' to '{target_host['name']}'")
        return True

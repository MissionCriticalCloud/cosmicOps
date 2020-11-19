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

from unittest import TestCase
from unittest.mock import Mock, patch

from cs import CloudStackException

from cosmicops import CosmicOps, CosmicVM, CosmicHost


class TestCosmicVM(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        slack_patcher = patch('cosmicops.log.Slack')
        self.mock_slack = slack_patcher.start()
        self.addCleanup(slack_patcher.stop)

        sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self._vm_json = {
            'id': 'v1',
            'name': 'vm1',
            'instancename': 'i-1-VM',
            'hostname': 'host1',
            'maintenancepolicy': 'LiveMigrate',
            'isoid': 'iso1'
        }

        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret', dry_run=False)
        self.ops.wait_for_job = Mock(return_value=True)
        self.vm = CosmicVM(self.ops, self._vm_json)
        self.target_host = CosmicHost(self.ops, {'id': 'h1', 'name': 'host1'})

    def test_stop(self):
        self.assertTrue(self.vm.stop())
        self.ops.cs.stopVirtualMachine.assert_called_with(id=self.vm['id'])

    def test_stop_with_shutdown_policy(self):
        self._vm_json['maintenancepolicy'] = 'ShutdownAndStart'
        self.assertTrue(self.vm.stop())
        self.ops.cs.stopVirtualMachine.assert_called_with(id=self.vm['id'])

    def test_stop_dry_run(self):
        self.vm.dry_run = True
        self.assertTrue(self.vm.stop())
        self.ops.cs.stopVirtualMachine.assert_not_called()

    def test_stop_failure(self):
        self.vm._ops.wait_for_job = Mock(return_value=False)
        self.assertFalse(self.vm.stop())

    def test_start(self):
        self.assertTrue(self.vm.start())
        self.ops.cs.startVirtualMachine.assert_called_with(id=self.vm['id'])

    def test_start_dry_run(self):
        self.vm.dry_run = True
        self.assertTrue(self.vm.start())
        self.ops.cs.startVirtualMachine.assert_not_called()

    def test_start_failure(self):
        self.vm._ops.wait_for_job = Mock(return_value=False)
        self.assertFalse(self.vm.start())

    def test_get_affinity_groups(self):
        self.cs_instance.listAffinityGroups.return_value = {'affinitygroup': [{'id': 'a1'}]}
        self.assertEqual([{'id': 'a1'}], self.vm.get_affinity_groups())

    def test_get_affinity_groups_exception(self):
        self.cs_instance.listAffinityGroups.side_effect = CloudStackException(response=Mock())
        self.assertEqual([], self.vm.get_affinity_groups())

    def test_migrate(self):
        self.assertTrue(self.vm.migrate(self.target_host))
        self.cs_instance.detachIso.assert_called_with(virtualmachineid=self.vm['id'])
        self.cs_instance.migrateVirtualMachine.assert_called_with(virtualmachineid=self.vm['id'],
                                                                  hostid=self.target_host['id'])
        self.cs_instance.migrateSystemVm.assert_not_called()

    def test_migrate_dry_run(self):
        self.vm.dry_run = True
        self.assertTrue(self.vm.migrate(self.target_host))
        self.cs_instance.detachIso.assert_not_called()
        self.cs_instance.migrateVirtualMachine.assert_not_called()
        self.cs_instance.migrateSystemVm.assert_not_called()

    def test_migrate_systemvm(self):
        del (self.vm._data['instancename'])
        self.assertTrue(self.vm.migrate(self.target_host))
        self.cs_instance.detachIso.assert_not_called()
        self.cs_instance.migrateVirtualMachine.assert_not_called()
        self.cs_instance.migrateSystemVm.assert_called_with(virtualmachineid=self.vm['id'],
                                                            hostid=self.target_host['id'])

    def test_migrate_with_volume(self):
        self.assertTrue(self.vm.migrate(self.target_host, with_volume=True))
        self.cs_instance.migrateVirtualMachine.assert_not_called()
        self.cs_instance.migrateVirtualMachineWithVolume.assert_called_with(virtualmachineid=self.vm['id'],
                                                                            hostid=self.target_host['id'])

    def test_migrate_with_migrate_virtual_machine_failure(self):
        self.cs_instance.migrateVirtualMachine.return_value = None
        self.assertFalse(self.vm.migrate(self.target_host))

    def test_migrate_with_migrate_system_vm_failure(self):
        del (self.vm._data['instancename'])
        self.cs_instance.migrateSystemVm.return_value = None
        self.assertFalse(self.vm.migrate(self.target_host))

    def test_migrate_with_job_failure(self):
        self.vm._ops.wait_for_job = Mock(return_value=False)
        self.assertFalse(self.vm.migrate(self.target_host))

    def test_get_volumes(self):
        self.cs_instance.listVolumes.return_value = {'volume': [{'id': 'v1'}]}
        self.assertEqual([{'id': 'v1'}], self.vm.get_volumes())

    def test_refresh(self):
        self.vm.refresh()
        self.cs_instance.listVirtualMachines.assert_called_with(id='v1')

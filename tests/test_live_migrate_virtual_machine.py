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
from unittest.mock import patch, Mock, call

from click.testing import CliRunner

import live_migrate_virtual_machine
from cosmicops.objects import CosmicCluster, CosmicHost, CosmicVM


class TestLiveMigrateVirtualMachine(TestCase):
    def setUp(self):
        co_patcher = patch('live_migrate_virtual_machine.CosmicOps')
        cs_patcher = patch('live_migrate_virtual_machine.CosmicSQL')
        sleep_patcher = patch('time.sleep', return_value=None)
        self.co = co_patcher.start()
        self.cs = cs_patcher.start()
        sleep_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.addCleanup(cs_patcher.stop)
        self.addCleanup(sleep_patcher.stop)
        self.co_instance = self.co.return_value
        self.cs_instance = self.cs.return_value
        self.runner = CliRunner()

        self._setup_mocks()

    def _setup_mocks(self):
        self.target_cluster = CosmicCluster(Mock(), {
            'id': 'tc1',
            'name': 'target_cluster'
        })
        self.vm = CosmicVM(Mock(), {
            'name': 'vm',
            'domain': 'domain',
            'zonename': 'zone',
            'hostid': 'sh1',
            'hostname': 'destination_host',
            'instancename': 'i-VM-1',
            'serviceofferingname': 'service_offering_EVO',
            'state': 'Running'
        })
        self.source_host = CosmicHost(Mock(), {
            'id': 'sh1',
            'name': 'source_host',
            'clusterid': 'sc1'
        })
        self.source_cluster = CosmicCluster(Mock(), {
            'id': 'sc1',
            'name': 'source_cluster'
        })
        self.destination_host = CosmicHost(Mock(), {
            'id': 'dh1',
            'name': 'destination_host',
            'clusterid': 'tc1'
        })

        self.co_instance.get_cluster.side_effect = [self.target_cluster, self.source_cluster]
        self.co_instance.get_vm.return_value = self.vm
        self.co_instance.get_host.return_value = self.source_host
        self.target_cluster.find_migration_host = Mock(return_value=self.destination_host)
        self.source_host.get_disks = Mock(return_value={'path1': {'path': 'path1', 'size': '1234'}})
        self.cs_instance.get_volume_size.return_value = ('name', 'path1', 'uuid', 'voltype', '1234')
        self.vm.migrate = Mock(return_value=True)
        self.vm.refresh = Mock()

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=False, log_to_slack=True)
        self.cs.assert_called_with(server='profile', dry_run=False)

        self.co_instance.get_cluster.assert_has_calls(
            [call(name='target_cluster'), call(id=self.source_host['clusterid'])])
        self.co_instance.get_vm.assert_called_with(name='vm', is_project_vm=False)
        self.co_instance.get_host.assert_called_with(id=self.vm['hostid'])
        self.cs_instance.update_zwps_to_cwps.assert_not_called()
        self.cs_instance.update_service_offering_of_vm.assert_not_called()
        self.target_cluster.find_migration_host.assert_called_with(self.vm)
        self.source_host.get_disks.assert_called_with(self.vm)
        self.cs_instance.get_volume_size.assert_called_with('path1')
        self.cs_instance.update_volume_size.assert_not_called()
        self.vm.migrate.assert_called_with(self.destination_host, with_volume=True)
        self.vm.refresh.assert_called()
        self.cs_instance.add_vm_to_affinity_group.assert_not_called()

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['-p', 'profile', 'vm', 'target_cluster']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=True, log_to_slack=False)
        self.cs.assert_called_with(server='profile', dry_run=True)

        self.co_instance.get_cluster.assert_has_calls(
            [call(name='target_cluster'), call(id=self.source_host['clusterid'])])
        self.co_instance.get_vm.assert_called_with(name='vm', is_project_vm=False)
        self.co_instance.get_host.assert_called_with(id=self.vm['hostid'])
        self.cs_instance.update_zwps_to_cwps.assert_not_called()
        self.cs_instance.update_service_offering_of_vm.assert_not_called()
        self.target_cluster.find_migration_host.assert_called_with(self.vm)
        self.source_host.get_disks.assert_not_called()
        self.cs_instance.get_volume_size.assert_not_called()
        self.cs_instance.update_volume_size.assert_not_called()
        self.vm.migrate.assert_not_called()
        self.vm.refresh.assert_not_called()
        self.cs_instance.add_vm_to_affinity_group.assert_not_called()

    def test_failures(self):
        self.co_instance.get_cluster.side_effect = None
        self.co_instance.get_cluster.return_value = None
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_cluster.assert_called()

        self._setup_mocks()
        self.co_instance.get_vm.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_vm.assert_called()

        self._setup_mocks()
        self.co_instance.get_host.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_host.assert_called()

        self._setup_mocks()
        self.co_instance.get_cluster.reset_mock()
        self.co_instance.get_cluster.side_effect = [self.target_cluster, []]
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.assertEqual(2, self.co_instance.get_cluster.call_count)

        self._setup_mocks()
        self.co_instance.get_cluster.reset_mock()
        self.source_cluster['id'] = self.target_cluster['id']
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.assertEqual(2, self.co_instance.get_cluster.call_count)
        self.target_cluster.find_migration_host.assert_not_called()

        self._setup_mocks()
        self.target_cluster.find_migration_host.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.target_cluster.find_migration_host.assert_called()

        self._setup_mocks()
        self.vm.migrate.return_value = False
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.vm.migrate.assert_called()

        self._setup_mocks()
        self.vm['hostname'] = self.source_host['name']
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)
        self.vm.migrate.assert_called()

    def test_destination_dc(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--destination-dc', 'EQXAMS2', 'vm',
                                                'target_cluster']).exit_code)

        self.cs_instance.update_service_offering_of_vm.assert_called_with(self.vm['instancename'],
                                                                          'service_offering_EQXAMS2')

        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--destination-dc', 'DUMMY', 'vm',
                                                'target_cluster']).exit_code)

    def test_volume_size_update(self):
        self.source_host.get_disks.return_value = {'path1': {'path': 'path1', 'size': '4321'}}

        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)

        self.cs_instance.update_volume_size.assert_called_with(self.vm['instancename'], 'path1', '4321')

    def test_zwps_to_cwps(self):
        self.cs_instance.update_zwps_to_cwps.return_value = True
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--zwps-to-cwps', 'vm',
                                                'target_cluster']).exit_code)
        self.cs_instance.update_zwps_to_cwps.assert_called_with(self.vm['instancename'], 'MCC_v1.CWPS')

        self._setup_mocks()
        self.cs_instance.update_zwps_to_cwps.return_value = False
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--zwps-to-cwps', 'vm',
                                                'target_cluster']).exit_code)

    def test_wait_for_running_state(self):
        def refresh_effect():
            self.vm._data['state'] = 'Running' if self.vm.refresh.call_count == 2 else 'Error'

        self.vm.refresh.side_effect = refresh_effect
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_cluster']).exit_code)

    def test_add_affinity_group(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--add-affinity-group', 'afgroup1', 'vm',
                                                'target_cluster']).exit_code)
        self.cs_instance.add_vm_to_affinity_group.assert_called_with(self.vm['instancename'], 'afgroup1')

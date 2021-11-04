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

import live_migrate_virtual_machine_volumes
from cosmicops.objects import CosmicCluster, CosmicHost, CosmicVM, CosmicStoragePool, CosmicVolume


class TestLiveMigrateVirtualMachineVolumes(TestCase):
    def setUp(self):
        co_patcher = patch('live_migrate_virtual_machine_volumes.CosmicOps')
        cs_patcher = patch('live_migrate_virtual_machine_volumes.CosmicSQL')
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
        self.vm = CosmicVM(Mock(), {
            'name': 'vm',
            'domain': 'domain',
            'zonename': 'zone',
            'hostid': 'sh1',
            'maintenancepolicy': 'LiveMigrate',
            'instancename': 'i-VM-1'
        })
        self.host = CosmicHost(Mock(), {
            'id': 'sh1',
            'name': 'host',
            'clusterid': 'sc1'
        })
        self.cluster = CosmicCluster(Mock(), {
            'id': 'sc1',
            'name': 'cluster'
        })
        self.source_storage_pool = CosmicStoragePool(Mock(), {
            'id': 'ssp1',
            'name': 'source_pool',
            'scope': 'CLUSTER'
        })
        self.target_storage_pool = CosmicStoragePool(Mock(), {
            'id': 'tsp1',
            'name': 'target_pool',
            'scope': 'CLUSTER'
        })
        self.volume = CosmicVolume(Mock(), {
            'id': 'v1',
            'name': 'volume1',
            'storageid': 'ssp1',
            'storage': 'source_pool',
            'state': 'Ready'
        })

        self.co_instance.get_storage_pool.side_effect = [self.target_storage_pool, self.source_storage_pool]
        self.co_instance.get_vm.return_value = self.vm
        self.co_instance.get_host.return_value = self.host
        self.co_instance.get_cluster.return_value = self.cluster

        self.host.get_disks = Mock(return_value={'path1': {'path': 'path1', 'size': '1234'}})
        self.host.set_iops_limit = Mock(return_value=True)
        self.host.merge_backing_files = Mock(return_value=True)
        self.cs_instance.get_volume_size.return_value = ('name', 'path1', 'uuid', 'voltype', '1234')
        self.vm.get_volumes = Mock(return_value=[self.volume])
        self.volume.migrate = Mock(return_value=True)
        self.volume.refresh = Mock()

        self.co_instance.get_storage_pool.reset_mock()
        self.co_instance.get_vm.reset_mock()
        self.co_instance.get_host.reset_mock()
        self.co_instance.get_cluster.reset_mock()
        self.cs_instance.get_volume_size.reset_mock()

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=False, log_to_slack=True)
        self.cs.assert_called_with(server='profile', dry_run=False)

        self.co_instance.get_storage_pool.assert_has_calls(
            [call(name='target_pool'), call(id=self.volume['storageid'])])
        self.co_instance.get_vm.assert_called_with(name='vm', is_project_vm=False)
        self.co_instance.get_host.assert_called_with(id=self.vm['hostid'])
        self.co_instance.get_cluster.assert_called_with(id=self.host['clusterid'])
        self.cs_instance.update_zwps_to_cwps.assert_not_called()
        self.host.get_disks.assert_called_with(self.vm)
        self.cs_instance.get_volume_size.assert_called_with('path1')
        self.cs_instance.update_volume_size.assert_not_called()
        self.host.set_iops_limit.assert_has_calls([call(self.vm, 1000), call(self.vm, 0)])
        self.host.merge_backing_files.assert_called_with(self.vm)
        self.vm.get_volumes.assert_called()
        self.volume.migrate.assert_called_with(self.target_storage_pool, live_migrate=True, source_host=self.host, vm=self.vm)
        self.volume.refresh.assert_called()

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['-p', 'profile', 'vm', 'target_pool']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=True, log_to_slack=False)
        self.cs.assert_called_with(server='profile', dry_run=True)

        self.co_instance.get_storage_pool.assert_has_calls(
            [call(name='target_pool'), call(id=self.volume['storageid'])])
        self.co_instance.get_vm.assert_called_with(name='vm', is_project_vm=False)
        self.co_instance.get_host.assert_called_with(id=self.vm['hostid'])
        self.co_instance.get_cluster.assert_called_with(id=self.host['clusterid'])
        self.cs_instance.update_zwps_to_cwps.assert_not_called()
        self.host.get_disks.assert_not_called()
        self.cs_instance.get_volume_size.assert_not_called()
        self.cs_instance.update_volume_size.assert_not_called()
        self.vm.get_volumes.assert_called()
        self.volume.migrate.assert_not_called()
        self.volume.refresh.assert_not_called()

    def test_failures(self):
        self.co_instance.get_storage_pool.side_effect = None
        self.co_instance.get_storage_pool.return_value = None
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.co_instance.get_storage_pool.assert_called()

        self._setup_mocks()
        self.co_instance.get_vm.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.co_instance.get_vm.assert_called()

        self._setup_mocks()
        self.co_instance.get_host.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.co_instance.get_host.assert_called()

        self._setup_mocks()
        self.co_instance.get_cluster.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.co_instance.get_cluster.assert_called()

        self._setup_mocks()
        self.host.set_iops_limit.return_value = False
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.host.set_iops_limit.assert_called()

        self._setup_mocks()
        self.host.merge_backing_files.return_value = False
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.host.merge_backing_files.assert_called()

    def test_continues(self):
        self.volume['storageid'] = self.target_storage_pool['id']
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.assertEqual(1, self.co_instance.get_storage_pool.call_count)

        self._setup_mocks()
        self.co_instance.get_storage_pool.side_effect = [self.target_storage_pool, None]
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.assertEqual(2, self.co_instance.get_storage_pool.call_count)
        self.volume.migrate.assert_not_called()

        self._setup_mocks()
        self.source_storage_pool['scope'] = 'Host'
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.assertEqual(2, self.co_instance.get_storage_pool.call_count)
        self.volume.migrate.assert_not_called()

        self._setup_mocks()
        self.volume.migrate.return_value = False
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)
        self.volume.migrate.assert_called()
        self.volume.refresh.assert_not_called()

    def test_zwps_to_cwps(self):
        self.cs_instance.update_zwps_to_cwps.return_value = True
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', '--zwps-to-cwps', 'vm',
                                                'target_pool']).exit_code)
        self.cs_instance.update_zwps_to_cwps.assert_called_with('MCC_v1.CWPS', instance_name=self.vm['instancename'])

        self._setup_mocks()
        self.cs_instance.update_zwps_to_cwps.return_value = False
        self.assertEqual(1, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', '--zwps-to-cwps', 'vm',
                                                'target_pool']).exit_code)

    def test_volume_size_update(self):
        self.host.get_disks.return_value = {'path1': {'path': 'path1', 'size': '4321'}}

        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)

        self.cs_instance.update_volume_size.assert_called_with(self.vm['instancename'], 'path1', '4321')

    def test_wait_for_ready_state(self):
        def refresh_effect():
            self.volume._data['state'] = 'Ready' if self.volume.refresh.call_count == 2 else 'Error'

        self.volume.refresh.side_effect = refresh_effect
        self.assertEqual(0, self.runner.invoke(live_migrate_virtual_machine_volumes.main,
                                               ['--exec', '-p', 'profile', 'vm', 'target_pool']).exit_code)

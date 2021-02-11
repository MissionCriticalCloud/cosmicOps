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
from unittest.mock import patch, Mock

from click.testing import CliRunner

import migrate_virtual_machine
from cosmicops.objects import CosmicCluster, CosmicHost, CosmicStoragePool, CosmicVolume, CosmicVM, \
    CosmicServiceOffering


class TestMigrateVirtualMachine(TestCase):
    def setUp(self):
        co_patcher = patch('migrate_virtual_machine.CosmicOps')
        cs_patcher = patch('migrate_virtual_machine.CosmicSQL')
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
            'id': 'tc',
            'name': 'target_cluster'
        })

        self.vm = CosmicVM(Mock(), {
            'id': 'vm',
            'name': 'vm',
            'domain': 'domain',
            'zonename': 'zone',
            'hostid': 'h1',
            'hostname': 'host',
            'instancename': 'i-VM-1',
            'serviceofferingid': 'so1',
            'serviceofferingname': 'service_offering_EVO',
            'state': 'Running'
        })

        self.host = CosmicHost(Mock(), {
            'id': 'h1',
            'name': 'host'
        })

        self.source_storage_pool = CosmicStoragePool(Mock(), {
            'id': 'ssp',
            'name': 'source_storage_pool',
            'scope': 'HOST'
        })

        self.target_storage_pool = CosmicStoragePool(Mock(), {
            'id': 'tsp',
            'name': 'target_storage_pool',
            'tags': 'storage_tags',
            'scope': 'CLUSTER'
        })

        self.service_offering = CosmicServiceOffering(Mock(), {
            'id': 'so1',
            'tags': 'storage_tags'
        })

        self.volume = CosmicVolume(Mock(), {
            'id': 'v1',
            'name': 'volume1',
            'state': 'Ready',
            'storage': 'source_storage_pool'
        })

        self.co_instance.get_cluster.return_value = self.target_cluster
        self.co_instance.get_vm.return_value = self.vm
        self.co_instance.get_service_offering.return_value = self.service_offering
        self.co_instance.get_storage_pool.return_value = self.source_storage_pool
        self.target_cluster.get_storage_pools = Mock(return_value=[self.target_storage_pool])
        self.target_cluster.find_migration_host = Mock(return_value=self.host)

        self.vm.get_volumes = Mock(return_value=[self.volume])
        self.vm.stop = Mock(return_value=True)
        self.vm.start = Mock(return_value=True)
        self.volume.migrate = Mock(return_value=True)
        self.volume.refresh = Mock()

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=False, log_to_slack=True)

        self.co_instance.get_cluster.assert_called_with(name='target_cluster')
        self.co_instance.get_vm.assert_called_with(name='vm', is_project_vm=False)
        self.target_cluster.get_storage_pools.assert_called()
        self.co_instance.get_service_offering.assert_called_with(id=self.service_offering['id'])
        self.vm.stop.assert_called()
        self.vm.get_volumes.assert_called_with()
        self.co_instance.get_storage_pool(name=self.volume['storage'])
        self.volume.migrate.assert_called_with(self.target_storage_pool)
        self.volume.refresh.assert_called()
        self.target_cluster.find_migration_host.assert_called_with(self.vm)
        self.vm.start.assert_called_with(self.host)

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['vm', 'target_cluster']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=True, log_to_slack=False)

    def test_with_stopped_vm(self):
        self.vm['state'] = 'Stopped'

        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)

        self.vm.stop.assert_not_called()
        self.target_cluster.find_migration_host.assert_not_called()
        self.vm.start.assert_not_called()

    def test_wait_for_ready_state(self):
        def refresh_effect():
            self.volume._data['state'] = 'Ready' if self.volume.refresh.call_count == 2 else 'Error'

        self.volume.refresh.side_effect = refresh_effect
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)

    def test_destination_dc(self):
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--destination-dc', 'EQXAMS2', 'vm',
                                                'target_cluster']).exit_code)

        self.cs_instance.update_service_offering_of_vm.assert_called_with(self.vm['instancename'],
                                                                          'service_offering_EQXAMS2')

        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--destination-dc', 'DUMMY', 'vm',
                                                'target_cluster']).exit_code)

    def test_destination_so(self):
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', '-p', 'profile', '--destination-so', 'large_offering', 'vm',
                                                'target_cluster']).exit_code)

        self.cs_instance.update_service_offering_of_vm.assert_called_with(self.vm['instancename'],
                                                                          'large_offering')

    def test_failures(self):
        self.co_instance.get_cluster.return_value = None
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_cluster.assert_called_with(name='target_cluster')

        self._setup_mocks()
        self.co_instance.get_vm.return_value = None
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_vm.assert_called_with(name='vm', is_project_vm=False)

        self._setup_mocks()
        self.target_cluster.get_storage_pools.return_value = []
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.target_cluster.get_storage_pools.assert_called()

        self._setup_mocks()
        self.target_storage_pool['tags'] = 'mismatch'
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_service_offering.assert_called_with(id=self.vm['serviceofferingid'])

        self._setup_mocks()
        self.vm.stop.return_value = False
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.vm.stop.assert_called()

        self._setup_mocks()
        self.co_instance.get_storage_pool.return_value = None
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_storage_pool.assert_called_with(name=self.volume['storage'])

        self._setup_mocks()
        self.volume.migrate.return_value = False
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.volume.migrate.assert_called_with(self.target_storage_pool)

        self._setup_mocks()
        self.target_cluster.find_migration_host.return_value = None
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.target_cluster.find_migration_host.assert_called_with(self.vm)

        self._setup_mocks()
        self.vm.start.return_value = False
        self.assertEqual(1, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.vm.start.assert_called_with(self.host)

    def test_continues(self):
        del self.service_offering['tags']
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)

        self._setup_mocks()
        self.co_instance.get_storage_pool.reset_mock()
        self.volume['storage'] = self.target_storage_pool['name']
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.co_instance.get_storage_pool.assert_not_called()
        self.volume.migrate.assert_not_called()

        self._setup_mocks()
        self.source_storage_pool['scope'] = 'ZONE'
        self.assertEqual(0, self.runner.invoke(migrate_virtual_machine.main,
                                               ['--exec', 'vm', 'target_cluster']).exit_code)
        self.volume.migrate.assert_not_called()

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

from cosmicops import CosmicOps
from cosmicops.objects import CosmicCluster, CosmicVM, CosmicSystemVM, CosmicServiceOffering


class TestCosmicCluster(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret')
        self.cluster = CosmicCluster(self.ops, {
            'id': 'c1',
            'name': 'cluster1'
        })

    def test_get_all_hosts(self):
        self.cs_instance.listHosts.return_value = [
            {
                'id': 'h1',
                'name': 'host1'
            }, {
                'id': 'h2',
                'name': 'host2'
            }
        ]

        hosts = self.cluster.get_all_hosts()
        self.assertEqual(2, len(hosts))
        self.assertEqual({'id': 'h1', 'name': 'host1'}, hosts[0]._data)
        self.assertEqual({'id': 'h2', 'name': 'host2'}, hosts[1]._data)

    def test_get_storage_pools(self):
        self.cs_instance.listStoragePools.return_value = [
            {
                'id': 'p1',
                'name': 'pool1'
            }
        ]

        self.assertDictEqual({'id': 'p1', 'name': 'pool1'}, self.cluster.get_storage_pools()[0]._data)

    def test_find_migration_host(self):
        self.cs_instance.listHosts.return_value = [
            {
                'id': 'h1',
                'name': 'same_host',
                'resourcestate': 'Enabled',
                'state': 'Up',
                'memorytotal': 1073741824,
                'memoryallocated': 0,
                'dedicated': False
            }, {
                'id': 'h2',
                'name': 'disabled_host',
                'resourcestate': 'Disabled',
                'state': 'Up',
                'memorytotal': 1073741824,
                'memoryallocated': 0,
                'dedicated': False
            }, {
                'id': 'h3',
                'name': 'disconnected_host',
                'resourcestate': 'Enabled',
                'state': 'Disconnected',
                'memorytotal': 1073741824,
                'memoryallocated': 0,
                'dedicated': False
            }, {
                'id': 'h4',
                'name': 'migration_host',
                'resourcestate': 'Enabled',
                'state': 'Up',
                'memorytotal': 1073741824,
                'memoryallocated': 0,
                'dedicated': False
            }, {
                'id': 'h_d',
                'name': 'migration_host_dedicated',
                'resourcestate': 'Enabled',
                'state': 'Up',
                'memorytotal': 1073741824,
                'memoryallocated': 0,
                'affinitygroupid': 123,
                'dedicated': True
            }
        ]

        vm = CosmicVM(Mock(), {
            'id': 'vm1',
            'memory': 512,
            'hostname': 'same_host',
            'instancename': 'i-VM-1'
        })
        vm.get_affinity_groups = Mock(return_value=[])

        # Test generic VM
        self.assertEqual(self.cluster.find_migration_host(vm)['name'], 'migration_host')

        # Test generic VM with non-ExplicitDedication type affinity group
        vm.get_affinity_groups.return_value = [{'type': 'test'}]
        self.assertEqual(self.cluster.find_migration_host(vm)['name'], 'migration_host')

        # Test dedicated vm and matching hypervisor
        vm.get_affinity_groups.return_value = [{'type': 'ExplicitDedication', 'id': 123}]
        self.assertEqual(self.cluster.find_migration_host(vm)['name'], 'migration_host_dedicated')

        # Test dedicated vm and non-matching hypervisor
        vm.get_affinity_groups.return_value = [{'type': 'ExplicitDedication', 'id': 999}]
        self.assertIsNone(self.cluster.find_migration_host(vm))

        # System VM without 'memory' attribute
        system_vm = CosmicSystemVM(Mock(), {
            'id': 'svm1',
            'hostname': 'same_host',
            'serviceofferingid': 'so1'
        })
        system_vm.get_affinity_groups = Mock(return_value=[])

        self.ops.get_service_offering = Mock(return_value=CosmicServiceOffering(Mock(), {'memory': 512}))
        self.assertEqual(self.cluster.find_migration_host(system_vm)['name'], 'migration_host')
        self.assertEqual(512, system_vm['memory'])

        # System VM without service offering details
        self.ops.get_service_offering.return_value = None
        self.assertEqual(self.cluster.find_migration_host(system_vm)['name'], 'migration_host')
        self.assertEqual(1024, system_vm['memory'])

        # No hosts with enough memory available
        self.cs_instance.listHosts.return_value = [
            {
                'id': 'h1',
                'name': 'low_mem_host',
                'resourcestate': 'Enabled',
                'state': 'Up',
                'memorytotal': 1073741824,
                'memoryallocated': 805306368,
                'dedicated': False
            }
        ]

        self.assertIsNone(self.cluster.find_migration_host(vm))

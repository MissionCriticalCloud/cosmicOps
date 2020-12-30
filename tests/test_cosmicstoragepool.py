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
from cosmicops.objects import CosmicStoragePool


class TestCosmicStoragePool(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret')

        self.storage_pool = CosmicStoragePool(self.ops, {
            'id': 'p1',
            'name': 'pool1',
            'ipaddress': 'ip_address',
            'path': 'path'
        })

    def test_orphaned_volumes(self):
        self.cs_instance.listVolumes.return_value = [
            {
                'id': 'v1',
                'name': 'attached_volume',
                'vmname': 'vm1'
            }, {
                'id': 'v2',
                'name': 'detached_volume',
            }
        ]

        self.assertEqual([{'id': 'v2', 'name': 'detached_volume'}], self.storage_pool.get_orphaned_volumes())

    def test_orphaned_volumes_empty_response(self):
        self.cs_instance.listVolumes.return_value = [
            {
                'id': 'v1',
                'name': 'attached_volume',
                'vmname': 'vm1'
            }
        ]

        self.assertFalse(self.storage_pool.get_orphaned_volumes())

    def test_get_file_list(self):
        host_mock = Mock()
        host_mock.execute.side_effect = [
            Mock(stdout='/ip_address:/path /mount/storage_pool_path nfs4 list_of_options 0 0\n'),
            Mock(stdout='1\t/mount/storage_pool_path/orphan_path\n2\t/mount/storage_pool_path/something_else\n')
        ]

        self.assertDictEqual({'orphan_path': '1', 'something_else': '2'}, self.storage_pool.get_file_list(host_mock))

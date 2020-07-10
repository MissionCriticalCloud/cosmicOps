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
from unittest.mock import patch

from cosmicops import CosmicOps, CosmicCluster


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
        self.cs_instance.listHosts.return_value = {
            'host': [{
                'id': 'h1',
                'name': 'host1'
            }, {
                'id': 'h2',
                'name': 'host2'
            }]
        }

        hosts = self.cluster.get_all_hosts()
        self.assertEqual(2, len(hosts))
        self.assertEqual({'id': 'h1', 'name': 'host1'}, hosts[0]._host)
        self.assertEqual({'id': 'h2', 'name': 'host2'}, hosts[1]._host)

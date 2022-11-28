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

from click.testing import CliRunner

import hosts
from cosmicops.objects import CosmicCluster, CosmicHost
from cosmicops import CosmicOps


class TestHosts(TestCase):
    def setUp(self):
        co_patcher = patch('hosts.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()
        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret')

        self._setup_mocks()

    def _setup_mocks(self):
        self.cluster = CosmicCluster(Mock(), {
            'id': 'c1',
            'name': 'cluster-c1'
        })
        self.host1 = CosmicHost(Mock(), {
            'id': 'h1',
            'name': 'cluster-hv01',
            'resourcestate': 'Enabled'
        })
        self.host2 = CosmicHost(Mock(), {
            'id': 'h2',
            'name': 'cluster-hv02',
            'resourcestate': 'Enabled'
        })
        self.host1.disable = Mock(return_value=True)
        self.host1.enable = Mock(return_value=True)
        self.host2.disable = Mock(return_value=True)
        self.host2.enable = Mock(return_value=True)
        self.co_instance.get_cluster.return_value = self.cluster
        self.co_instance.get_host.return_value = self.host1
        self.co_instance.get_host.side_effect = [self.host1, self.host2]
        self.cluster.get_all_hosts = Mock(return_value=[self.host1, self.host2])

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(hosts.main, ['cluster-c1']).exit_code)
        self.co.assert_called_with(profile='config', dry_run=True, log_to_slack=True)
        self.co_instance.get_cluster.assert_called_with(name='cluster-c1')

    def test_main_failure(self):
        self.assertEqual(1, self.runner.invoke(hosts.main, ['cluster-c2']).exit_code)

    def test_disable(self):
        self.assertEqual(0, self.runner.invoke(hosts.main, ['--exec', '--disable', '-h', '1', 'cluster-c1']).exit_code)

    def test_disable_not_called(self):
        self._setup_mocks()
        self.host1 = CosmicHost(Mock(), {
            'id': 'h1',
            'name': 'cluster-hv01',
            'resourcestate': 'Disabled'
        })
        self.host1.disable = Mock(return_value=True)
        self.assertEqual(0, self.runner.invoke(hosts.main, ['--exec', '--disable', '-h', '1', 'cluster-c1']).exit_code)
        self.host1.disable.assert_not_called()

    def test_dry_run(self):
        self.assertEqual(0, self.runner.invoke(hosts.main, ['--disable', '-h', '1', 'cluster-c1']).exit_code)
        self.co.assert_called_with(profile='config', dry_run=True, log_to_slack=True)

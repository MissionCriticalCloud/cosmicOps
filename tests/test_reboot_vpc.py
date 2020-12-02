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

import reboot_vpc
from cosmicops import CosmicNetwork, CosmicVPC


class TestRebootVPC(TestCase):
    def setUp(self):
        co_patcher = patch('reboot_vpc.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()

        self._setup_mocks()

    def _setup_mocks(self):
        self.network = CosmicNetwork(Mock(), {
            'id': 'n1',
            'name': 'network1',
            'vpcid': 'v1'
        })

        self.vpc = CosmicVPC(Mock(), {
            'id': 'v1',
            'name': 'vpc1',
            'domain': 'domain',
            'zonename': 'zone'
        })

        self.co_instance.get_vpc.return_value = self.vpc
        self.co_instance.get_network.return_value = self.network

        self.vpc.restart = Mock(return_value=True)

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(reboot_vpc.main,
                                               ['--exec', 'vpc1']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=False, log_to_slack=True)

        self.co_instance.get_vpc.assert_called_with(name='vpc1')
        self.co_instance.get_network.assert_not_called()
        self.vpc.restart.assert_called()

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(reboot_vpc.main,
                                               ['vpc']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=True, log_to_slack=False)

    def test_parameters(self):
        self.assertEqual(1, self.runner.invoke(reboot_vpc.main,
                                               ['--exec', '--uuid', '--network-uuid', 'router1']).exit_code)
        self.co.assert_not_called()

    def test_with_uuid(self):
        self.assertEqual(0, self.runner.invoke(reboot_vpc.main,
                                               ['--exec', '--uuid', 'v1']).exit_code)

        self.co_instance.get_vpc.assert_called_with(id='v1')
        self.co_instance.get_network.assert_not_called()
        self.vpc.restart.assert_called()

    def test_with_network_uuid(self):
        self.assertEqual(0, self.runner.invoke(reboot_vpc.main,
                                               ['--exec', '--network-uuid', 'n1']).exit_code)

        self.co_instance.get_network.assert_called_with(id='n1')
        self.co_instance.get_vpc.assert_called_with(id=self.network['vpcid'])
        self.vpc.restart.assert_called()

    def test_failures(self):
        self.co_instance.get_vpc.return_value = None
        self.assertEqual(1, self.runner.invoke(reboot_vpc.main, ['--exec', 'vpc1']).exit_code)
        self.co_instance.get_vpc.assert_called_with(name='vpc1')

        self.assertEqual(1, self.runner.invoke(reboot_vpc.main, ['--exec', '--uuid', 'v1']).exit_code)
        self.co_instance.get_vpc.assert_called_with(id='v1')

        self.assertEqual(1, self.runner.invoke(reboot_vpc.main, ['--exec', '--network-uuid', 'n1']).exit_code)
        self.co_instance.get_vpc.assert_called_with(id=self.network['vpcid'])

        self._setup_mocks()
        self.co_instance.get_network.return_value = None
        self.assertEqual(1, self.runner.invoke(reboot_vpc.main, ['--exec', '--network-uuid', 'n1']).exit_code)
        self.co_instance.get_network.assert_called_with(id='n1')

        self._setup_mocks()
        self.vpc.restart.return_value = False
        self.assertEqual(1, self.runner.invoke(reboot_vpc.main, ['--exec', 'vpc1']).exit_code)
        self.vpc.restart.assert_called()

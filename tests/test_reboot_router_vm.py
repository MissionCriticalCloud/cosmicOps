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

import reboot_router_vm
from cosmicops import CosmicCluster, CosmicHost, CosmicVPC, CosmicRouter


class TestRebootRouterVM(TestCase):
    def setUp(self):
        co_patcher = patch('reboot_router_vm.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()

        self._setup_mocks()

    def _setup_mocks(self):
        self.cluster = CosmicCluster(Mock(), {
            'id': 'c1',
            'name': 'cluster1'
        })

        self.host = CosmicHost(Mock(), {
            'id': 'h1',
            'name': 'host1',
            'clusterid': 'c1'
        })

        self.router = CosmicRouter(Mock(), {
            'id': 'r1',
            'name': 'router1',
            'domain': 'domain',
            'hostid': 'h1',
            'vpcid': 'v1',
            'requiresupgrade': False
        })

        self.vpc = CosmicVPC(Mock(), {
            'id': 'v1',
            'name': 'vpc1'
        })

        self.co_instance.get_router.return_value = self.router
        self.co_instance.get_host.return_value = self.host
        self.co_instance.get_cluster.return_value = self.cluster
        self.co_instance.get_vpc.return_value = self.vpc

        self.vpc.restart = Mock(return_value=True)
        self.router.reboot = Mock(return_value=True)

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(reboot_router_vm.main, ['--exec', 'router1']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=False, log_to_slack=True)

        self.co_instance.get_router.assert_called_with(name='router1', is_project_router=False)
        self.co_instance.get_host.assert_called_with(id=self.router['hostid'])
        self.co_instance.get_cluster.assert_called_with(id=self.host['clusterid'])

        self.co_instance.get_vpc.assert_not_called()
        self.vpc.restart.assert_not_called()

        self.co_instance.get_network.assert_not_called()

        self.router.reboot.asset_called()

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(reboot_router_vm.main, ['router1']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=True, log_to_slack=False)

    def test_only_when_required(self):
        self.assertEqual(0, self.runner.invoke(reboot_router_vm.main,
                                               ['--exec', '--only-when-required', 'router1']).exit_code)

        self.router.reboot.assert_not_called()

    def test_vpc_cleanup(self):
        self.assertEqual(0, self.runner.invoke(reboot_router_vm.main, ['--exec', '--cleanup', 'router1']).exit_code)

        self.co_instance.get_vpc.assert_called_with(id=self.router['vpcid'])
        self.vpc.restart.assert_called()

        self.router.reboot.assert_not_called()

    def test_failures(self):
        self.co_instance.get_router.return_value = None
        self.assertEqual(1, self.runner.invoke(reboot_router_vm.main, ['--exec', 'router1']).exit_code)
        self.co_instance.get_router.assert_called_with(name='router1', is_project_router=False)

        self._setup_mocks()
        self.co_instance.get_host.return_value = None
        self.assertEqual(1, self.runner.invoke(reboot_router_vm.main, ['--exec', 'router1']).exit_code)
        self.co_instance.get_host.assert_called_with(id=self.router['hostid'])

        self._setup_mocks()
        self.co_instance.get_cluster.return_value = None
        self.assertEqual(1, self.runner.invoke(reboot_router_vm.main, ['--exec', 'router1']).exit_code)
        self.co_instance.get_cluster.assert_called_with(id=self.host['clusterid'])

        self._setup_mocks()
        self.router['vpcid'] = ''
        self.assertEqual(1, self.runner.invoke(reboot_router_vm.main, ['--exec', '--cleanup', 'router1']).exit_code)
        self.co_instance.get_cluster.assert_called_with(id=self.host['clusterid'])
        self.co_instance.get_vpc.assert_not_called()

        self._setup_mocks()
        self.co_instance.get_vpc.return_value = None
        self.assertEqual(1, self.runner.invoke(reboot_router_vm.main, ['--exec', '--cleanup', 'router1']).exit_code)
        self.co_instance.get_vpc.assert_called_with(id=self.router['vpcid'])

        self._setup_mocks()
        self.vpc.restart.return_value = False
        self.assertEqual(1, self.runner.invoke(reboot_router_vm.main, ['--exec', '--cleanup', 'router1']).exit_code)
        self.vpc.restart.assert_called()

        self._setup_mocks()
        self.router.reboot.return_value = False
        self.assertEqual(1, self.runner.invoke(reboot_router_vm.main, ['--exec', 'router1']).exit_code)
        self.router.reboot.assert_called()

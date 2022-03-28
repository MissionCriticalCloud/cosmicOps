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

import live_migrate_router
from cosmicops.objects import CosmicCluster, CosmicHost, CosmicSystemVM


class TestLiveMigrateRouter(TestCase):
    def setUp(self):
        co_patcher = patch('live_migrate_router.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()

        self._setup_mocks()

    def _setup_mocks(self):
        self.router = CosmicSystemVM(Mock(), {
            'name': 'router',
            'hostid': 'sh1',
            'hostname': 'kvm1'
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
        self.destination_host = CosmicHost(Mock(), {
            'id': 'dh1',
            'name': 'destination_host',
            'clusterid': 'tc1'
        })

        self.co_instance.get_system_vm.return_value = self.router
        self.co_instance.get_host.return_value = self.host
        self.co_instance.get_cluster.return_value = self.cluster
        self.cluster.find_migration_host = Mock(return_value=self.destination_host)
        self.router.migrate = Mock(return_value=True)

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_router.main,
                                               ['--exec', 'router']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=False, log_to_slack=True)

        self.co_instance.get_system_vm.assert_called_with(name='router')
        self.co_instance.get_host.assert_called_with(id=self.router['hostid'])
        self.co_instance.get_cluster.assert_called_with(id=self.host['clusterid'])
        self.cluster.find_migration_host.assert_called_with(self.router)
        self.router.migrate.assert_called_with(self.destination_host)

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_router.main,
                                               ['router']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=True, log_to_slack=False)

    def test_failures(self):
        self.co_instance.get_system_vm.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_router.main,
                                               ['--exec', 'router']).exit_code)
        self.co_instance.get_system_vm.assert_called()

        self._setup_mocks()
        self.co_instance.get_host.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_router.main,
                                               ['--exec', 'router']).exit_code)
        self.co_instance.get_host.assert_called()

        self._setup_mocks()
        self.co_instance.get_cluster.reset_mock()
        self.co_instance.get_cluster.return_value = None
        self.assertEqual(1, self.runner.invoke(live_migrate_router.main,
                                               ['--exec', 'router']).exit_code)
        self.co_instance.get_cluster.assert_called()

        self._setup_mocks()
        self.cluster.find_migration_host.return_value = []
        self.assertEqual(1, self.runner.invoke(live_migrate_router.main,
                                               ['--exec', 'router']).exit_code)
        self.cluster.find_migration_host.assert_called()

        self._setup_mocks()
        self.router.migrate.return_value = False
        self.assertEqual(1, self.runner.invoke(live_migrate_router.main,
                                               ['--exec', 'router']).exit_code)
        self.router.migrate.assert_called()

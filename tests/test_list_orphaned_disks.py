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

import list_orphaned_disks
from cosmicops.objects import CosmicStoragePool, CosmicCluster, CosmicZone


class TestListOrphanedDisks(TestCase):
    def setUp(self):
        co_patcher = patch('cosmicops.list_orphaned_disks.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()
        self.host = Mock()
        self.storage_pool = Mock()

    def _setup_mocks(self):
        orphans = [{
            'name': 'orphan1',
            'domain': 'orphan1_domain',
            'account': 'orphan1_account',
            'path': 'orphan1_path',
            'size': 1073741824
        }]

        self.storage_pool = CosmicStoragePool(Mock(), {'name': 'storage_pool1'})
        self.storage_pool.get_file_list = Mock(return_value={'orphan1_path': '1'})
        self.storage_pool.get_orphaned_volumes = Mock(return_value=orphans)
        self.cluster = CosmicCluster(Mock(), {'name': 'cluster1'})
        self.cluster.get_storage_pools = Mock(return_value=[self.storage_pool])
        self.cluster.get_all_hosts = Mock(return_value=[self.host])
        self.zone = CosmicZone(Mock(), {'id': 'z1', 'name': 'zone1'})
        self.co_instance.get_all_clusters.return_value = [self.cluster]
        self.co_instance.get_cluster.return_value = self.cluster
        self.co_instance.get_zone.return_value = self.zone

    def test_main(self):
        self._setup_mocks()
        result = self.runner.invoke(list_orphaned_disks.main, ['--profile', 'profile', 'zone1'])

        self.co.assert_called_with(profile='profile', dry_run=False)
        self.co_instance.get_all_clusters.assert_called_with(self.zone)
        self.storage_pool.get_file_list.assert_called_with(self.host)
        self.storage_pool.get_orphaned_volumes.assert_called_once()
        self.assertEqual(0, result.exit_code)

    def test_main_with_cluster(self):
        self._setup_mocks()
        result = self.runner.invoke(list_orphaned_disks.main, ['--profile', 'profile', '--cluster', 'cluster1', 'zone1'])
        self.co_instance.get_cluster.assert_called_with(name='cluster1', zone=self.zone)
        self.assertEqual(0, result.exit_code)

    def test_main_without_cluster_data(self):
        self.co_instance.get_all_clusters.return_value = []
        result = self.runner.invoke(list_orphaned_disks.main, ['--profile', 'profile', 'zone1'])
        self.assertEqual(0, result.exit_code)

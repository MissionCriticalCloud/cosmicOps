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

import migrate_offline_volumes
from cosmicops.objects import CosmicCluster, CosmicStoragePool, CosmicVolume


class TestMigrateOfflineVolumes(TestCase):
    def setUp(self):
        co_patcher = patch('migrate_offline_volumes.CosmicOps')
        cs_patcher = patch('migrate_offline_volumes.CosmicSQL')
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
        self.source_cluster = CosmicCluster(Mock(), {
            'id': 'sc',
            'name': 'source_cluster'
        })

        self.destination_cluster = CosmicCluster(Mock(), {
            'id': 'dc',
            'name': 'destination_cluster'
        })

        self.source_storage_pool = CosmicStoragePool(Mock(), {
            'id': 'ssp',
            'name': 'source_storage_pool'
        })

        self.destination_storage_pool = CosmicStoragePool(Mock(), {
            'id': 'dsp',
            'name': 'destination_storage_pool'
        })

        self.volume = CosmicVolume(Mock(), {
            'id': 'v1',
            'name': 'volume1',
            'state': 'Ready',
            'storage': 'source_storage_pool',
            'diskofferingname': 'disk_test_offering'
        })

        self.co_instance.get_cluster.side_effect = [self.source_cluster, self.destination_cluster]
        self.source_cluster.get_storage_pools = Mock(return_value=[self.source_storage_pool])
        self.destination_cluster.get_storage_pools = Mock(return_value=[self.destination_storage_pool])
        self.source_storage_pool.get_volumes = Mock(return_value=[self.volume])
        self.volume.migrate = Mock(return_value=True)
        self.volume.refresh = Mock()

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=False)

        self.co_instance.get_cluster.assert_has_calls([call(name='source_cluster'), call(name='destination_cluster')],
                                                      True)
        self.source_cluster.get_storage_pools.assert_called()
        self.destination_cluster.get_storage_pools.assert_called()
        self.source_storage_pool.get_volumes.assert_called_with(False)
        self.volume.migrate.assert_called_with(self.destination_storage_pool)

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['source_cluster', 'destination_cluster']).exit_code)

        self.co.assert_called_with(profile='config', dry_run=True)

    def test_ignore_volumes(self):
        ignore_volume = CosmicVolume(Mock(), {
            'id': 'iv',
            'name': 'ignore_volume',
            'state': 'Ready',
            'storage': 'source_storage_pool'
        })
        ignore_volume.migrate = Mock()
        self.source_storage_pool.get_volumes = Mock(return_value=[ignore_volume, self.volume])

        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', '--ignore-volumes', 'iv', 'source_cluster',
                                                'destination_cluster']).exit_code)

        ignore_volume.migrate.assert_not_called()
        self.volume.migrate.assert_called()

    def test_skip_disk_offerings(self):
        skip_volume = CosmicVolume(Mock(), {
            'id': 'sv',
            'name': 'skip_volume',
            'state': 'Ready',
            'storage': 'source_storage_pool',
            'diskofferingname': 'SKIP_ME'
        })
        skip_volume.migrate = Mock()

        self.source_storage_pool.get_volumes = Mock(return_value=[skip_volume, self.volume])

        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', '--skip-disk-offerings', 'SKIP_ME', 'source_cluster',
                                                'destination_cluster']).exit_code)

        skip_volume.migrate.assert_not_called()
        self.volume.migrate.assert_called()

    def test_wait_for_ready_state(self):
        def refresh_effect():
            self.volume._data['state'] = 'Ready' if self.volume.refresh.call_count == 2 else 'Error'

        self.volume.refresh.side_effect = refresh_effect
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)

    def test_failures(self):
        self.co_instance.get_cluster.side_effect = [None, None]
        self.assertEqual(1, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.co_instance.get_cluster.assert_has_calls([call(name='source_cluster'), call(name='destination_cluster')])

        self._setup_mocks()
        self.co_instance.get_cluster.side_effect = [self.source_cluster, None]
        self.assertEqual(1, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.co_instance.get_cluster.assert_called_with(name='destination_cluster')

        self._setup_mocks()
        self.source_cluster.get_storage_pools.side_effect = IndexError
        self.assertEqual(1, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.source_cluster.get_storage_pools.assert_called()

        self._setup_mocks()
        self.destination_cluster.get_storage_pools.side_effect = IndexError
        self.assertEqual(1, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.destination_cluster.get_storage_pools.assert_called()

    def test_continues(self):
        del self.volume['storage']
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.volume.migrate.assert_not_called()

        self._setup_mocks()
        self.volume['storage'] = self.destination_storage_pool['name']
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.volume.migrate.assert_not_called()

        self._setup_mocks()
        self.volume['state'] = 'Error'
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.volume.migrate.assert_not_called()

        self._setup_mocks()
        self.volume['vmname'] = 'Mock VM'
        self.volume['vmstate'] = 'Running'
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.volume.migrate.assert_not_called()

        self._setup_mocks()
        self.volume.migrate.return_value = False
        self.assertEqual(0, self.runner.invoke(migrate_offline_volumes.main,
                                               ['--exec', 'source_cluster', 'destination_cluster']).exit_code)
        self.volume.migrate.assert_called()

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

from cosmicops import CosmicOps, CosmicVolume, CosmicStoragePool


class TestCosmicVolume(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret', dry_run=False)
        self.ops.wait_for_job = Mock(return_value=True)
        self.cs_instance.migrateVolume.return_value = {'jobid': 1}

        self.volume = CosmicVolume(self.ops, {
            'id': 'vol1',
            'name': 'volume1'
        })

        self.storage_pool = CosmicStoragePool(self.ops, {
            'id': 'p1',
            'name': 'pool1'
        })

    def test_refresh(self):
        self.volume.refresh()
        self.cs_instance.listVolumes.assert_called_with(fetch_list=True, id='vol1')

    def test_migrate(self):
        self.assertTrue(self.volume.migrate(self.storage_pool))
        self.cs_instance.migrateVolume.assert_called_with(volumeid=self.volume['id'], storageid=self.storage_pool['id'],
                                                          livemigrate=False)

        self.ops.wait_for_job.return_value = False
        self.assertFalse(self.volume.migrate(self.storage_pool))

    def test_migrate_dry_run(self):
        self.volume._ops.dry_run = True
        self.volume.dry_run = True

        self.assertTrue(self.volume.migrate(self.storage_pool))
        self.cs_instance.migrateVolume.assert_not_called()

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

from cosmicops import CosmicOps
from cosmicops.objects import CosmicVPC


class TestCosmicVPC(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret', dry_run=False)
        self.ops.wait_for_job = Mock(return_value=True)
        self.vpc = CosmicVPC(self.ops, {
            'id': 'v1',
            'name': 'vpc1'
        })

    def test_restart(self):
        self.assertTrue(self.vpc.restart())
        self.ops.cs.restartVPC.assert_called_with(id=self.vpc['id'])

    def test_restart_dry_run(self):
        self.vpc.dry_run = True
        self.assertTrue(self.vpc.restart())
        self.ops.cs.restartVPC.assert_not_called()

    def test_restart_failure(self):
        self.ops.wait_for_job.return_value = False
        self.assertFalse(self.vpc.restart())
        self.ops.wait_for_job.assert_called()

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
from cosmicops.objects import CosmicSystemVM, CosmicHost


class TestCosmicSystemVM(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        slack_patcher = patch('cosmicops.log.Slack')
        self.mock_slack = slack_patcher.start()
        self.addCleanup(slack_patcher.stop)

        sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self._systemvm_json = {
            'id': 'svm1',
            'name': 's-1-VM',
            'hostname': 'host1'
        }

        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret', dry_run=False)
        self.ops.wait_for_job = Mock(return_value=True)
        self.systemvm = CosmicSystemVM(self.ops, self._systemvm_json)
        self.target_host = CosmicHost(self.ops, {'id': 'h1', 'name': 'host1'})

    def test_stop(self):
        self.assertTrue(self.systemvm.stop())
        self.ops.cs.stopSystemVm.assert_called_with(id=self.systemvm['id'])

    def test_stop_dry_run(self):
        self.systemvm.dry_run = True
        self.assertTrue(self.systemvm.stop())
        self.ops.cs.stopSystemVm.assert_not_called()

    def test_stop_failure(self):
        self.systemvm._ops.wait_for_job = Mock(return_value=False)
        self.assertFalse(self.systemvm.stop())

    def test_start(self):
        self.assertTrue(self.systemvm.start())
        self.ops.cs.startSystemVm.assert_called_with(id=self.systemvm['id'])

    def test_start_dry_run(self):
        self.systemvm.dry_run = True
        self.assertTrue(self.systemvm.start())
        self.ops.cs.startSystemVm.assert_not_called()

    def test_start_failure(self):
        self.systemvm._ops.wait_for_job = Mock(return_value=False)
        self.assertFalse(self.systemvm.start())

    def test_destroy(self):
        self.assertTrue(self.systemvm.destroy())
        self.ops.cs.destroySystemVm.assert_called_with(id=self.systemvm['id'])

    def test_destroy_dry_run(self):
        self.systemvm.dry_run = True
        self.assertTrue(self.systemvm.destroy())
        self.ops.cs.destroySystemVm.assert_not_called()

    def test_destroy_failure(self):
        self.systemvm._ops.wait_for_job = Mock(return_value=False)
        self.assertFalse(self.systemvm.destroy())

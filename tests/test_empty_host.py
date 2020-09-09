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

import empty_host


class TestEmptyHost(TestCase):
    def setUp(self):
        co_patcher = patch('empty_host.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()

    def test_main(self):
        host_mock = Mock()
        host_mock.empty.return_value = (1, 1, 0)
        self.co_instance.get_host_by_name.return_value = host_mock

        result = self.runner.invoke(empty_host.main, ['--exec', 'host1'])
        self.co.assert_called_with(profile='config', dry_run=False)
        self.co_instance.get_host_by_name.assert_called_with('host1')
        host_mock.empty.assert_called()
        self.assertEqual(0, result.exit_code)

    def test_fail_on_empty_host_response(self):
        self.co_instance.get_host_by_name.return_value = []

        result = self.runner.invoke(empty_host.main, ['--exec', 'host1'])
        self.co_instance.get_host_by_name.assert_called_with('host1')
        self.assertEqual(1, result.exit_code)

    def test_dry_run(self):
        host_mock = Mock()
        host_mock.empty.return_value = (1, 1, 0)
        self.co_instance.get_host_by_name.return_value = host_mock

        result = self.runner.invoke(empty_host.main, ['host1'])
        self.co.assert_called_with(profile='config', dry_run=True)
        self.assertEqual(0, result.exit_code)

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
from cosmicops.objects.host import CosmicHost, RebootAction


class TestEmptyHost(TestCase):
    def setUp(self):
        co_patcher = patch('cosmicops.empty_host.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value

        slack_patcher = patch('cosmicops.log.Slack')
        self.mock_slack = slack_patcher.start()
        self.addCleanup(slack_patcher.stop)

        self.runner = CliRunner()
        self.host = CosmicHost(Mock(), {
            'id': 'h1',
            'name': 'host1'
        })
        self.host.empty = Mock(return_value=(1, 1, 0))
        self.host.reboot = Mock(return_value=True)
        self.host.set_uid_led = Mock()
        self.co_instance.get_host.return_value = self.host

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(empty_host.main, ['--exec', 'host1']).exit_code)
        self.co.assert_called_with(profile='config', dry_run=False)
        self.co_instance.get_host.assert_called_with(name='host1')
        self.host.empty.assert_called()
        self.host.reboot.assert_not_called()
        self.host.set_uid_led.assert_not_called()

    def test_fail_on_empty_host_response(self):
        self.co_instance.get_host.return_value = []

        self.assertEqual(1, self.runner.invoke(empty_host.main, ['--exec', 'host1']).exit_code)
        self.co_instance.get_host.assert_called_with(name='host1')

    def test_shutdown(self):
        self.assertEqual(0, self.runner.invoke(empty_host.main, ['--exec', '--shutdown', 'host1']).exit_code)
        self.host.reboot.assert_called_with(RebootAction.HALT)
        self.host.set_uid_led.assert_called_with(True)

    def test_shutdown_with_failed_hosts(self):
        self.host.empty.return_value = (2, 1, 1)

        self.assertEqual(0, self.runner.invoke(empty_host.main, ['--exec', '--shutdown', 'host1']).exit_code)
        self.host.reboot.assert_not_called()
        self.host.set_uid_led.assert_not_called()

    def test_shutdown_failure(self):
        self.host.reboot.return_value = False
        self.assertEqual(1, self.runner.invoke(empty_host.main, ['--exec', '--shutdown', 'host1']).exit_code)
        self.host.reboot.assert_called_with(RebootAction.HALT)

    def test_dry_run(self):
        host_mock = Mock()
        host_mock.empty.return_value = (1, 1, 0)
        self.co_instance.get_host.return_value = host_mock

        self.assertEqual(0, self.runner.invoke(empty_host.main, ['host1']).exit_code)
        self.co.assert_called_with(profile='config', dry_run=True)

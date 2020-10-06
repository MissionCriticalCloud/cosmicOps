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

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock

from testfixtures import tempdir

from cosmicops.log import CosmicLog, WARNING, ERROR, INFO


class TestCosmicLog(TestCase):
    def setUp(self):
        slack_patcher = patch('cosmicops.log.Slack')
        self.mock_slack = slack_patcher.start()
        self.addCleanup(slack_patcher.stop)
        self.slack_instance = self.mock_slack.return_value

        self.logging = CosmicLog()

    @tempdir()
    def test_load_from_config(self, tmp):
        config = (b"[slack]\n"
                  b"hookurl = https://test.url/slack/hook\n"
                  )

        tmp.write('config', config)
        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            self.assertEqual(self.slack_instance, self.logging._configure_slack())

        self.mock_slack.assert_called_with(url='https://test.url/slack/hook')

        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path('/dev/null')
            self.assertIsNone(self.logging._configure_slack())

    def test_log_to_slack(self):
        send_message_mock = Mock()
        self.logging._send_slack_message = send_message_mock
        self.logging._slack = self.slack_instance

        self.logging._log(INFO, 'info message', True)
        send_message_mock.assert_called_with('info message', 'good')

        self.logging._log(WARNING, 'warning message', True)
        send_message_mock.assert_called_with('warning message', 'warning')

        self.logging._log(ERROR, 'error message', True)
        send_message_mock.assert_called_with('error message', 'danger')

    def test_send_slack_message(self):
        self.logging._slack = self.slack_instance
        self.logging.slack_title = 'test_title'
        self.logging.slack_value = 'test_value'
        self.logging.task = 'test_task'
        self.logging.cluster = 'test_cluster'
        self.logging.instance_name = 'test_instance_name'
        self.logging.vm_name = 'test_vm_name'
        self.logging.zone_name = 'test_zone_name'

        self.logging._send_slack_message('test_message')

        call_args = self.slack_instance.post.call_args
        attachment = call_args[1]['attachments'][0]
        attachment_fields = attachment['fields']
        self.assertEqual('test_message', attachment['text'])
        self.assertEqual('good', attachment['color'])
        self.assertEqual('test_title', attachment_fields[1]['title'])
        self.assertEqual('test_value', attachment_fields[1]['value'])
        self.assertEqual('test_task', attachment_fields[2]['value'])
        self.assertEqual('test_cluster', attachment_fields[3]['value'])
        self.assertEqual('test_instance_name', attachment_fields[4]['value'])
        self.assertEqual('test_vm_name', attachment_fields[5]['value'])
        self.assertEqual('test_zone_name', attachment_fields[6]['value'])
        self.assertEqual('cosmicOps', call_args[1]['username'])

    def test_send_slack_message_failure(self):
        self.slack_instance.post.side_effect = RuntimeError
        self.logging._slack = self.slack_instance

        self.logging._send_slack_message('test_message_failure')

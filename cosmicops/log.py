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

import logging as logging_module
from datetime import datetime
from logging import DEBUG, WARNING, ERROR, INFO
from urllib.error import HTTPError, URLError

from slack_webhook import Slack

from cosmicops import get_config


class CosmicLog(object):
    def __init__(self):
        self._slack = self._configure_slack()
        self.slack_title = 'Undefined'
        self.slack_value = 'Undefined'
        self.task = 'Undefined'
        self.instance_name = 'Undefined'
        self.vm_name = 'Undefined'
        self.cluster = 'Undefined'
        self.zone_name = 'Undefined'

    @staticmethod
    def _configure_slack():
        config = get_config()

        slack_hook_url = config.get('slack', 'hookurl', fallback=None)

        if slack_hook_url:
            return Slack(url=slack_hook_url)
        else:
            print(f"warning: No Slack connection details found in configuration file")
            return None

    def _log(self, log_level, message, log_to_slack):
        logging_module.log(log_level, message)

        if log_to_slack and self._slack:
            if log_level == ERROR:
                color = 'danger'
            elif log_level == WARNING:
                color = 'warning'
            else:
                color = 'good'

            self._send_slack_message(message, color)

    def _send_slack_message(self, message, color='good'):
        attachments = []
        attachment = {'text': message, 'color': color, 'mrkdwn_in': ['text', 'pretext', 'fields'], 'mrkdwn': 'true',
                      'fields': [
                          {
                              'title': 'Timestamp',
                              'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                          },
                          {
                              'title': str(self.slack_title),
                              'value': str(self.slack_value),
                              'short': 'true'
                          },
                          {
                              'title': 'Task',
                              'value': self.task,
                              'short': 'true'
                          },
                          {
                              'title': 'Cluster',
                              'value': self.cluster,
                              'short': 'true'
                          },
                          {
                              'title': 'Instance ID',
                              'value': self.instance_name,
                              'short': 'true'
                          },
                          {
                              'title': 'VM name',
                              'value': self.vm_name,
                              'short': 'true'
                          },
                          {
                              'title': 'Zone',
                              'value': self.zone_name,
                              'short': 'true'
                          }
                      ]}

        try:
            attachments.append(attachment)
            self._slack.post(attachments=attachments, icon_emoji=':robot_face:', username='cosmicOps')
        except (HTTPError, URLError):
            print('warning: Slack post failed.')

    # noinspection PyPep8Naming
    @staticmethod
    def getLogger():
        return logging_module.getLogger()

    def info(self, message, log_to_slack=False):
        self._log(INFO, message, log_to_slack)

    def debug(self, message, log_to_slack=False):
        self._log(DEBUG, message, log_to_slack)

    def warning(self, message, log_to_slack=False):
        self._log(WARNING, message, log_to_slack)

    def error(self, message, log_to_slack=False):
        self._log(ERROR, message, log_to_slack)


logging = CosmicLog()

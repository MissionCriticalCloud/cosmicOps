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
from unittest.mock import Mock, patch, call

from click.testing import CliRunner

import rolling_reboot
from cosmicops.host import RebootAction, CosmicHost


class TestRollingReboot(TestCase):
    def setUp(self):
        co_patcher = patch('rolling_reboot.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value

        slack_patcher = patch('cosmicops.log.Slack')
        self.mock_slack = slack_patcher.start()
        self.addCleanup(slack_patcher.stop)

        sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self.runner = CliRunner()

    def _mock_cluster_with_hosts(self):
        self.cluster = Mock()
        self.co_instance.get_cluster_by_name.return_value = self.cluster

        self.hosts = []
        for i in range(3):
            host = CosmicHost(Mock(), {
                'id': f'h{i}',
                'name': f'host{i}',
                'clusterid': 'c1',
                'state': 'Up',
                'resourcestate': 'Enabled',
                'zonename': 'zone1'
            })
            host.get_all_vms = Mock(return_value=[1, 2, 3])
            host.empty = Mock(return_value=(0, 0, 0))
            host.disable = Mock(return_value=True)
            host.enable = Mock(return_value=True)
            host.reboot = Mock(return_value=True)
            host.wait_until_offline = Mock(return_value=None)
            host.wait_until_online = Mock(return_value=None)
            host.copy_file = Mock(return_value=None)
            host.execute = Mock(return_value=None)

            self.hosts.append(host)

        self.cluster.get_all_hosts.return_value = self.hosts

    def test_main(self):
        self._mock_cluster_with_hosts()

        result = self.runner.invoke(rolling_reboot.main, ['--exec', 'cluster1'])
        self.assertEqual(0, result.exit_code)

        self.co.assert_called_with(profile='config', dry_run=False, log_to_slack=True)
        self.co_instance.get_cluster_by_name.assert_called_with('cluster1')

        self.cluster.get_all_hosts.assert_called()

        for host in self.hosts:
            host.disable.assert_called()
            host.reboot.assert_called_with(RebootAction.REBOOT)
            host.wait_until_offline.assert_called()
            host.wait_until_online.assert_called()
            host.enable.assert_called()

    def test_ignore_hosts(self):
        self._mock_cluster_with_hosts()

        result = self.runner.invoke(rolling_reboot.main, ['--exec', '--ignore-hosts', 'host2', 'cluster1'])
        self.assertEqual(0, result.exit_code)

        self.hosts[0].reboot.assert_called_with(RebootAction.REBOOT)
        self.hosts[1].reboot.assert_called_with(RebootAction.REBOOT)
        self.hosts[2].reboot.assert_not_called()

    def test_only_hosts(self):
        self._mock_cluster_with_hosts()

        result = self.runner.invoke(rolling_reboot.main, ['--exec', '--only-hosts', 'host1,host2', 'cluster1'])
        self.assertEqual(0, result.exit_code)

        self.hosts[0].reboot.assert_not_called()
        self.hosts[1].reboot.assert_called_with(RebootAction.REBOOT)
        self.hosts[2].reboot.assert_called_with(RebootAction.REBOOT)

    def test_skip_os_version(self):
        self._mock_cluster_with_hosts()
        self.hosts[0]._host['hypervisorversion'] = 'CentOS 7.5.1804'
        self.hosts[1]._host['hypervisorversion'] = 'CentOS 7.7.1908'
        self.hosts[2]._host['hypervisorversion'] = 'CentOS 8.0.1905'

        result = self.runner.invoke(rolling_reboot.main, ['--exec', '--skip-os-version', 'CentOS 7', 'cluster1'])
        self.assertEqual(0, result.exit_code)

        self.hosts[0].reboot.assert_not_called()
        self.hosts[1].reboot.assert_not_called()
        self.hosts[2].reboot.assert_called_with(RebootAction.REBOOT)

    def test_scripts(self):
        self._mock_cluster_with_hosts()

        result = self.runner.invoke(rolling_reboot.main, ['--exec',
                                                          '--pre-empty-script', 'pre_empty_script.sh',
                                                          '--post-empty-script', 'post_empty_script.sh',
                                                          '--post-reboot-script', 'post_reboot_script.sh',
                                                          'cluster1'])
        self.assertEqual(0, result.exit_code)

        for host in self.hosts:
            host.copy_file.assert_has_calls([call('pre_empty_script.sh', '/tmp/pre_empty_script.sh', mode=0o755),
                                             call('post_empty_script.sh', '/tmp/post_empty_script.sh', mode=0o755),
                                             call('post_reboot_script.sh', '/tmp/post_reboot_script.sh', mode=0o755)])
            host.execute.assert_has_calls([call('/tmp/pre_empty_script.sh', sudo=True),
                                           call('/tmp/post_empty_script.sh', sudo=True),
                                           call('/tmp/post_reboot_script.sh', sudo=True)])

    def test_failures(self):
        # Cluster lookup failure
        self.co_instance.get_cluster_by_name.return_value = None

        result = self.runner.invoke(rolling_reboot.main, ['--exec', 'cluster1'])
        self.assertEqual(1, result.exit_code)

        # Host disable failure
        self._mock_cluster_with_hosts()
        self.hosts[0].disable = Mock(return_value=False)
        result = self.runner.invoke(rolling_reboot.main, ['--exec', 'cluster1'])
        self.assertEqual(1, result.exit_code)

        self.hosts[0].disable.assert_called()

        # Host disconnected
        self._mock_cluster_with_hosts()
        self.hosts[0]._host['state'] = 'Disconnected'
        result = self.runner.invoke(rolling_reboot.main, ['--exec', 'cluster1'])
        self.assertEqual(1, result.exit_code)

        self.hosts[0].disable.assert_called()

        # Test if script continues after host empty failure
        self._mock_cluster_with_hosts()
        self.hosts[0].empty = Mock(side_effect=[(5, 0, 5), (5, 5, 0)])
        result = self.runner.invoke(rolling_reboot.main, ['--exec', 'cluster1'])
        self.assertEqual(0, result.exit_code)

        self.hosts[0].empty.assert_called()
        self.hosts[0].reboot.assert_called()
        self.hosts[1].reboot.assert_called()
        self.hosts[2].reboot.assert_called()

        # Host reboot failure
        self._mock_cluster_with_hosts()
        self.hosts[0].reboot = Mock(return_value=False)
        result = self.runner.invoke(rolling_reboot.main, ['--exec', 'cluster1'])
        self.assertEqual(1, result.exit_code)

        self.hosts[0].reboot.assert_called()

        # Host enable failure
        self._mock_cluster_with_hosts()
        self.hosts[0].enable = Mock(return_value=False)
        result = self.runner.invoke(rolling_reboot.main, ['--exec', 'cluster1'])
        self.assertEqual(1, result.exit_code)

        self.hosts[0].enable.assert_called()

    def test_dry_run(self):
        self._mock_cluster_with_hosts()

        result = self.runner.invoke(rolling_reboot.main, ['cluster1'])
        self.assertEqual(0, result.exit_code)
        self.co.assert_called_with(profile='config', dry_run=True, log_to_slack=False)

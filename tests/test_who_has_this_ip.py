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
from unittest.mock import patch, call

from click.testing import CliRunner

import who_has_this_ip


class TestWhoHasThisIP(TestCase):
    def setUp(self):
        cs_patcher = patch('who_has_this_ip.CosmicSQL')
        self.cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.cs.return_value
        self.runner = CliRunner()
        self.cs_instance.get_ip_address_data.return_value = (
            ('network_name',
             'mac_address',
             'ipv4_address',
             'netmask',
             'broadcast_uri',
             'mode',
             'state',
             'created',
             'vm_name'),
        )

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(who_has_this_ip.main,
                                               ['-s', 'server_address', '-p', 'password', '192.168.1.1']).exit_code)
        self.cs.assert_called_with(server='server_address', database='cloud', port=3306, user='cloud',
                                   password='password', dry_run=False)
        self.cs_instance.get_ip_address_data.assert_called_with('192.168.1.1')
        self.cs_instance.get_ip_address_data_bridge.assert_not_called()
        self.cs_instance.get_ip_address_data_infra.assert_not_called()

    def test_argument_combinations(self):
        self.assertEqual(1, self.runner.invoke(who_has_this_ip.main,
                                               ['-s', 'server_address', '-a', '192.168.1.1']).exit_code)
        self.assertEqual(1, self.runner.invoke(who_has_this_ip.main, ['192.168.1.1']).exit_code)

    def test_all_databases(self):
        self.cs.get_all_dbs_from_config.return_value = ['server_address_1', 'server_address_2']
        self.assertEqual(0, self.runner.invoke(who_has_this_ip.main, ['--all-databases', '192.168.1.1']).exit_code)
        self.cs.assert_has_calls(
            [call(server='server_address_1', database='cloud', port=3306, user='cloud', password=None,
                  dry_run=False),
             call(server='server_address_2', database='cloud', port=3306, user='cloud', password=None,
                  dry_run=False)],
            any_order=True
        )
        self.cs_instance.get_ip_address_data.has_calls([call('192.168.1.1'), call('192.168.1.1')])

    def test_all_databases_with_empty_config(self):
        self.cs.get_all_dbs_from_config.return_value = []
        self.assertEqual(1, self.runner.invoke(who_has_this_ip.main, ['--all-databases', '192.168.1.1']).exit_code)

    def test_use_bridge_data(self):
        self.cs_instance.get_ip_address_data_bridge.return_value = (
            ('vm_name',
             'ipv4_address',
             'created',
             'network_name',
             'state'),
        )
        self.cs_instance.get_ip_address_data.return_value = ()

        self.assertEqual(0, self.runner.invoke(who_has_this_ip.main,
                                               ['-s', 'server_address', '-p', 'password', '192.168.1.1']).exit_code)
        self.cs_instance.get_ip_address_data.assert_called_with('192.168.1.1')
        self.cs_instance.get_ip_address_data_bridge.assert_called_with('192.168.1.1')
        self.cs_instance.get_ip_address_data_infra.assert_not_called()

    def test_use_infra_data(self):
        self.cs_instance.get_ip_address_data_infra.return_value = (
            ('vm_name',
             'vm_type',
             'state',
             'ipv4_address',
             'instance_id'),
        )
        self.cs_instance.get_ip_address_data.return_value = ()

        self.assertEqual(0, self.runner.invoke(who_has_this_ip.main,
                                               ['-s', 'server_address', '-p', 'password', '192.168.1.1']).exit_code)
        self.cs_instance.get_ip_address_data.assert_called_with('192.168.1.1')
        self.cs_instance.get_ip_address_data_bridge.assert_called_with('192.168.1.1')
        self.cs_instance.get_ip_address_data_infra.assert_called_with('192.168.1.1')

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

import who_has_this_mac


class TestWhoHasThisMAC(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.who_has_this_mac.CosmicSQL')
        self.cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.cs.return_value
        self.runner = CliRunner()
        self.cs_instance.get_mac_address_data.return_value = (
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
        self.assertEqual(0, self.runner.invoke(who_has_this_mac.main,
                                               ['-s', 'server_address', '-p', 'password',
                                                'aa:bb:cc:dd:ee:ff']).exit_code)
        self.cs.assert_called_with(server='server_address', database='cloud', port=3306, user='cloud',
                                   password='password', dry_run=False)
        self.cs_instance.get_mac_address_data.assert_called_with('aa:bb:cc:dd:ee:ff')

    def test_argument_combinations(self):
        self.assertEqual(1, self.runner.invoke(who_has_this_mac.main,
                                               ['-s', 'server_address', '-a', 'aa:bb:cc:dd:ee:ff']).exit_code)
        self.assertEqual(1, self.runner.invoke(who_has_this_mac.main, ['aa:bb:cc:dd:ee:ff']).exit_code)

    def test_all_databases(self):
        self.cs.get_all_dbs_from_config.return_value = ['server_address_1', 'server_address_2']
        self.assertEqual(0,
                         self.runner.invoke(who_has_this_mac.main, ['--all-databases', 'aa:bb:cc:dd:ee:ff']).exit_code)
        self.cs.assert_has_calls(
            [call(server='server_address_1', database='cloud', port=3306, user='cloud', password=None,
                  dry_run=False),
             call(server='server_address_2', database='cloud', port=3306, user='cloud', password=None,
                  dry_run=False)],
            any_order=True
        )
        self.cs_instance.get_ip_address_data.has_calls([call('aa:bb:cc:dd:ee:ff'), call('aa:bb:cc:dd:ee:ff')])

    def test_all_databases_with_empty_config(self):
        self.cs.get_all_dbs_from_config.return_value = []
        self.assertEqual(1,
                         self.runner.invoke(who_has_this_mac.main, ['--all-databases', 'aa:bb:cc:dd:ee:ff']).exit_code)

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
from unittest.mock import patch

from click.testing import CliRunner

import list_ha_workers


class TestListHAWorkers(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.list_ha_workers.CosmicSQL')
        tabulate_patcher = patch('cosmicops.list_ha_workers.tabulate')
        self.cs = cs_patcher.start()
        self.tabulate = tabulate_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.addCleanup(tabulate_patcher.stop)
        self.cs_instance = self.cs.return_value
        self.runner = CliRunner()
        self.workers = ((
                            'domain_1',
                            'vm_name_1',
                            'vm_type_1',
                            'Running',
                            'created_1',
                            'taken_1',
                            'step_1',
                            'host_1',
                            'mgt_server_1',
                            'ha_state_1'
                        ), (
                            'domain_2',
                            '',
                            'vm_type_2',
                            'Running',
                            'created_2',
                            'taken_2',
                            'step_2',
                            'host_2',
                            'mgt_server_2',
                            'ha_state_2'
                        ), (
                            'domain_3',
                            'vm_name_3',
                            'vm_type_3',
                            'Stopped',
                            'created_3',
                            'taken_3',
                            'step_3',
                            'host_3',
                            'mgt_server_3',
                            'ha_state_3'
                        ),)

        self.cs_instance.list_ha_workers.return_value = self.workers

    def test_main(self):
        self.assertEqual(0,
                         self.runner.invoke(list_ha_workers.main, ['-s', 'server_address', '-p', 'password']).exit_code)
        self.cs.assert_called_with(server='server_address', database='cloud', port=3306, user='cloud',
                                   password='password', dry_run=False)
        self.cs_instance.list_ha_workers.assert_called_with('')
        table_data = self.tabulate.call_args[0][0]
        flat_data = [worker for workers in table_data for worker in workers]
        self.assertIn('vm_name_1', flat_data)
        self.assertNotIn('vm_type_2', flat_data)
        self.assertIn('vm_name_3', flat_data)

    def test_non_running(self):
        self.assertEqual(0,
                         self.runner.invoke(list_ha_workers.main, ['-s', 'server_address', '--non-running']).exit_code)
        table_data = self.tabulate.call_args[0][0]
        flat_data = [worker for workers in table_data for worker in workers]
        self.assertNotIn('vm_name_1', flat_data)
        self.assertIn('vm_name_3', flat_data)

    def test_name_filter(self):
        self.assertEqual(0, self.runner.invoke(list_ha_workers.main,
                                               ['-s', 'server_address', '--name-filter', 'name_1']).exit_code)
        table_data = self.tabulate.call_args[0][0]
        flat_data = [worker for workers in table_data for worker in workers]
        self.assertIn('vm_name_1', flat_data)
        self.assertNotIn('vm_name_3', flat_data)

    def test_without_workers(self):
        self.cs_instance.list_ha_workers.return_value = []
        self.assertEqual(0, self.runner.invoke(list_ha_workers.main, ['-s', 'db_alias']).exit_code)

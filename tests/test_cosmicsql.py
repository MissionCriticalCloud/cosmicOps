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
import configparser
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, call, ANY

import pymysql
from testfixtures import tempdir

from cosmicops import CosmicSQL


class TestCosmicSQL(TestCase):
    def setUp(self):
        pymysql_connect_patcher = patch('pymysql.connect')
        self.mock_connect = pymysql_connect_patcher.start()
        self.addCleanup(pymysql_connect_patcher.stop)
        self.mock_cursor = self.mock_connect.return_value.cursor.return_value

        self.cs = CosmicSQL(server='localhost', password='password', dry_run=False)

    @tempdir()
    def test_load_from_config(self, tmp):
        config = (b"[testmariadb]\n"
                  b"host = 10.0.0.1\n"
                  b"port = 3706\n"
                  b"user = test_user\n"
                  b"password = test_password\n"
                  )

        tmp.write('config', config)
        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            cs = CosmicSQL(server='testmariadb')

        self.assertEqual('10.0.0.1', cs.server)
        self.assertEqual(3706, cs.port)
        self.assertEqual('test_user', cs.user)
        self.assertEqual('test_password', cs.password)

        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            self.assertRaises(RuntimeError, CosmicSQL, server='dummy')

    @tempdir()
    def test_load_from_config_with_defaults(self, tmp):
        config = (b"[testmariadb]\n"
                  b"password = test_password\n"
                  )

        tmp.write('config', config)
        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            cs = CosmicSQL(server='testmariadb')

        self.assertEqual('testmariadb', cs.server)
        self.assertEqual(3306, cs.port)
        self.assertEqual('cloud', cs.user)
        self.assertEqual('test_password', cs.password)

    @tempdir()
    def test_load_from_config_without_password(self, tmp):
        config = (b"[testmariadb]\n"
                  b"host = 10.0.0.1\n"
                  )

        tmp.write('config', config)
        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            self.assertRaises(configparser.NoOptionError, CosmicSQL, server='testmariadb')

    @tempdir()
    def test_get_all_dbs_from_config(self, tmp):
        config = (b"[db1]\n"
                  b"host = db1\n"
                  b"[db2]\n"
                  b"host = db2\n"
                  b"[db3]\n"
                  b"host = db3\n"
                  )

        tmp.write('config', config)
        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            all_dbs = CosmicSQL.get_all_dbs_from_config()

        self.assertListEqual(['db1', 'db2', 'db3'], all_dbs)

    def test_connect_failure(self):
        self.mock_connect.side_effect = pymysql.Error('Mock connection error')
        self.assertRaises(pymysql.Error, CosmicSQL, server='localhost', password='password')

    def test_kill_jobs_of_instance(self):
        self.assertTrue(self.cs.kill_jobs_of_instance('1'))

        self.mock_cursor.execute.assert_has_calls([
            call('DELETE FROM `async_job` WHERE `instance_id` = %s', ('1',)),
            call('DELETE FROM `vm_work_job` WHERE `vm_instance_id` = %s', ('1',)),
            call('DELETE FROM `sync_queue` WHERE `sync_objid` = %s', ('1',))
        ])
        self.assertEqual(3, self.mock_connect.return_value.commit.call_count)

    def test_kill_jobs_of_instance_dry_run(self):
        self.cs = CosmicSQL(server='localhost', password='password', dry_run=True)

        self.assertTrue(self.cs.kill_jobs_of_instance('1'))

        self.mock_cursor.execute.assert_has_calls([
            call('DELETE FROM `async_job` WHERE `instance_id` = %s', ('1',)),
            call('DELETE FROM `vm_work_job` WHERE `vm_instance_id` = %s', ('1',)),
            call('DELETE FROM `sync_queue` WHERE `sync_objid` = %s', ('1',))
        ])
        self.mock_connect.return_value.commit.assert_not_called()

    def test_kill_jobs_of_instance_query_failure(self):
        self.mock_cursor.execute.side_effect = pymysql.Error('Mock query error')

        self.assertFalse(self.cs.kill_jobs_of_instance('i-1-VM'))

    def test_list_ha_workers(self):
        self.assertIsNotNone(self.cs.list_ha_workers())

        self.mock_cursor.execute.assert_called_with(ANY)
        self.mock_cursor.fetchall.assert_called()

    def test_list_ha_workers_with_hostname(self):
        self.assertIsNotNone(self.cs.list_ha_workers('host1'))

        self.mock_cursor.execute.assert_called_with(ANY)

    def test_list_ha_workers_query_failure(self):
        self.mock_cursor.execute.side_effect = pymysql.Error('Mock query error')

        self.assertRaises(pymysql.Error, self.cs.list_ha_workers)
        self.mock_cursor.close.assert_called_once()

    def test_get_ip_address_data(self):
        self.cs.get_ip_address_data('192.168.1.1')
        self.assertIn("public_ip_address LIKE '%192.168.1.1%'", self.mock_cursor.execute.call_args[0][0])
        self.assertIn("ip4_address LIKE '%192.168.1.1%'", self.mock_cursor.execute.call_args[0][0])

    def test_get_ip_address_data_bridge(self):
        self.cs.get_ip_address_data_bridge('192.168.1.1')
        self.assertIn("public_ip_address LIKE '%192.168.1.1%'", self.mock_cursor.execute.call_args[0][0])

    def test_get_ip_address_data_infra(self):
        self.cs.get_ip_address_data_infra('192.168.1.1')
        self.assertIn("ip4_address LIKE '%192.168.1.1%'", self.mock_cursor.execute.call_args[0][0])

    def test_get_mac_address_data(self):
        self.cs.get_mac_address_data('aa:bb:cc:dd:ee:ff')
        self.assertIn("mac_address LIKE '%aa:bb:cc:dd:ee:ff%'", self.mock_cursor.execute.call_args[0][0])

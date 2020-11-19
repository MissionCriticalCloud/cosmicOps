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
from unittest.mock import patch, call, ANY, Mock

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
        config = (b"[dummy]\n"
                  b"foo = bar\n"
                  b"[db1]\n"
                  b"host = db1\n"
                  b"[db2]\n"
                  b"host = db2\n"
                  b"[db3]\n"
                  b"host = db3\n"
                  )

        tmp.write('config', config)
        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            self.assertListEqual(['db1', 'db2', 'db3'], CosmicSQL.get_all_dbs_from_config())

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
        self.assertIsNotNone(self.cs.get_ip_address_data('192.168.1.1'))

        self.assertIn("public_ip_address LIKE '%192.168.1.1%'", self.mock_cursor.execute.call_args[0][0])
        self.assertIn("ip4_address LIKE '%192.168.1.1%'", self.mock_cursor.execute.call_args[0][0])

    def test_get_ip_address_data_bridge(self):
        self.assertIsNotNone(self.cs.get_ip_address_data_bridge('192.168.1.1'))

        self.assertIn("user_ip_address.public_ip_address LIKE '%192.168.1.1%'",
                      self.mock_cursor.execute.call_args[0][0])

    def test_get_ip_address_data_infra(self):
        self.assertIsNotNone(self.cs.get_ip_address_data_infra('192.168.1.1'))

        self.assertIn("nics.ip4_address LIKE '%192.168.1.1%'", self.mock_cursor.execute.call_args[0][0])

    def test_get_mac_address_data(self):
        self.assertIsNotNone(self.cs.get_mac_address_data('aa:bb:cc:dd:ee:ff'))

        self.assertIn("mac_address LIKE '%aa:bb:cc:dd:ee:ff%'", self.mock_cursor.execute.call_args[0][0])

    def test_get_instance_id_from_name(self):
        self.assertIsNotNone(self.cs.get_instance_id_from_name('instance'))

        self.assertIn("instance_name = 'instance'", self.mock_cursor.execute.call_args[0][0])

    def test_get_disk_offering_id_from_name(self):
        self.assertIsNotNone(self.cs.get_disk_offering_id_from_name('disk_offering'))

        self.assertIn("name = 'disk_offering'", self.mock_cursor.execute.call_args[0][0])

    def test_get_service_offering_id_from_name(self):
        self.assertIsNotNone(self.cs.get_service_offering_id_from_name('service_offering'))

        self.assertIn("name = 'service_offering'", self.mock_cursor.execute.call_args[0][0])

    def test_get_affinity_group_id_from_name(self):
        self.assertIsNotNone(self.cs.get_affinity_group_id_from_name('affinity_group'))

        self.assertIn("name = 'affinity_group'", self.mock_cursor.execute.call_args[0][0])

    def test_update_zwps_to_cwps(self):
        self.cs.get_instance_id_from_name = Mock(return_value='instance_id')
        self.cs.get_disk_offering_id_from_name = Mock(return_value='disk_offering_id')

        self.assertTrue(self.cs.update_zwps_to_cwps('instance_name', 'disk_offering_name'))
        self.assertIn("disk_offering_id=", self.mock_cursor.execute.call_args[0][0])
        self.assertIn("instance_id=", self.mock_cursor.execute.call_args[0][0])
        self.assertEqual(('disk_offering_id', 'instance_id'), self.mock_cursor.execute.call_args[0][1])

    def test_update_service_offering_of_vm(self):
        self.cs.get_instance_id_from_name = Mock(return_value='instance_id')
        self.cs.get_service_offering_id_from_name = Mock(return_value='service_offering_id')

        self.assertTrue(self.cs.update_service_offering_of_vm('instance_name', 'service_offering_name'))
        self.assertIn("service_offering_id=", self.mock_cursor.execute.call_args[0][0])
        self.assertIn("id=", self.mock_cursor.execute.call_args[0][0])
        self.assertEqual(('service_offering_id', 'instance_id'), self.mock_cursor.execute.call_args[0][1])

    def test_get_volume_size(self):
        self.assertIsNotNone(self.cs.get_volume_size('path1'))

        self.assertIn("path = 'path1'", self.mock_cursor.execute.call_args[0][0])

    def test_update_volume_size(self):
        self.cs.get_instance_id_from_name = Mock(return_value='instance_id')

        self.assertTrue(self.cs.update_volume_size('instance_name', 'path', 4321))
        self.assertIn("size=", self.mock_cursor.execute.call_args[0][0])
        self.assertIn("instance_id=", self.mock_cursor.execute.call_args[0][0])
        self.assertIn("path=", self.mock_cursor.execute.call_args[0][0])
        self.assertEqual((4321, 'path', 'instance_id'), self.mock_cursor.execute.call_args[0][1])

    def test_add_vm_to_affinity_group(self):
        self.cs.get_instance_id_from_name = Mock(return_value='instance_id')
        self.cs.get_affinity_group_id_from_name = Mock(return_value='affinity_group_id')

        self.assertTrue(self.cs.add_vm_to_affinity_group('instance_name', 'affinity_group_name'))
        self.assertIn("(instance_id, affinity_group_id)", self.mock_cursor.execute.call_args[0][0])
        self.assertEqual(('instance_id', 'affinity_group_id'), self.mock_cursor.execute.call_args[0][1])

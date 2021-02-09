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
from unittest.mock import Mock, patch

from cs import CloudStackException
from requests.exceptions import ConnectionError
from testfixtures import tempdir

from cosmicops import CosmicOps
from cosmicops.objects import CosmicZone, CosmicPod
from cosmicops.objects.object import CosmicObject
# noinspection PyProtectedMember
from cosmicops.ops import _load_cloud_monkey_profile


class TestCosmicOps(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        slack_patcher = patch('cosmicops.log.Slack')
        self.mock_slack = slack_patcher.start()
        self.addCleanup(slack_patcher.stop)

        sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self.co = CosmicOps(endpoint='https://localhost', key='key', secret='secret')

    @patch('cosmicops.ops._load_cloud_monkey_profile')
    def test_init_with_profile(self, mock_load):
        mock_load.return_value = ('profile_endpoint', 'profile_key', 'profile_secret')
        CosmicOps(profile='config')
        self.mock_cs.assert_called_with('profile_endpoint', 'profile_key', 'profile_secret', 60)

    @tempdir()
    def test_load_cloud_monkey_profile(self, tmp):
        config = (b"[testprofile]\n"
                  b"url = http://localhost:8000/client/api\n"
                  b"apikey = test_api_key\n"
                  b"secretkey = test_secret_key\n"
                  )

        tmp.makedir('.cloudmonkey')
        tmp.write('.cloudmonkey/config', config)
        with patch('pathlib.Path.home') as path_home_mock:
            path_home_mock.return_value = Path(tmp.path)
            (endpoint, key, secret) = _load_cloud_monkey_profile('testprofile')

        self.assertEqual('http://localhost:8000/client/api', endpoint)
        self.assertEqual('test_api_key', key)
        self.assertEqual('test_secret_key', secret)

    @tempdir()
    def test_load_cloud_monkey_profile_with_default(self, tmp):
        config = (b"[core]\n"
                  b"profile = profile2\n\n"
                  b"[profile1]\n"
                  b"url = http://localhost:8000/client/api/1\n"
                  b"apikey = test_api_key_1\n"
                  b"secretkey = test_secret_key_1\n\n"
                  b"[profile2]\n"
                  b"url = http://localhost:8000/client/api/2\n"
                  b"apikey = test_api_key_2\n"
                  b"secretkey = test_secret_key_2\n"
                  )

        tmp.makedir('.cloudmonkey')
        tmp.write('.cloudmonkey/config', config)
        with patch('pathlib.Path.home') as path_home_mock:
            path_home_mock.return_value = Path(tmp.path)
            (endpoint, key, secret) = _load_cloud_monkey_profile('config')

        self.assertEqual('http://localhost:8000/client/api/2', endpoint)
        self.assertEqual('test_api_key_2', key)
        self.assertEqual('test_secret_key_2', secret)

    def test_cs_get_single_result(self):
        self.cs_instance.listFunction.return_value = [
            {
                'id': 'id_field',
                'name': 'name_field'
            }
        ]

        result = self.co._cs_get_single_result('listFunction', {'name': 'name_field'}, CosmicObject, 'type')
        self.cs_instance.listFunction.assert_called_with(fetch_list=True, name='name_field')
        self.assertIsInstance(result, CosmicObject)
        self.assertDictEqual({'id': 'id_field', 'name': 'name_field'}, result._data)

    def test_get_get_single_result_failure(self):
        self.cs_instance.listFunction.return_value = []
        self.assertIsNone(self.co._cs_get_single_result('listFunction', {}, CosmicObject, 'type'))

        self.cs_instance.listFunction.return_value = [{}, {}]
        self.assertIsNone(self.co._cs_get_single_result('listFunction', {}, CosmicObject, 'type'))

    def test_cs_get_all_results(self):
        self.cs_instance.listFunction.return_value = [
            {
                'id': 'id1',
                'name': 'name1'
            }, {
                'id': 'id2',
                'name': 'name2'
            }
        ]

        result = self.co._cs_get_all_results('listFunction', {}, CosmicObject, 'type')
        self.cs_instance.listFunction.assert_called_with(fetch_list=True)
        for i, item in enumerate(result):
            self.assertIsInstance(item, CosmicObject)
            self.assertDictEqual({'id': f'id{i + 1}', 'name': f'name{i + 1}'}, item._data)

    def test_get_vm(self):
        self.co._cs_get_single_result = Mock()

        self.co.get_vm(name='vm1')
        self.assertDictEqual({'name': 'vm1', 'listall': True}, self.co._cs_get_single_result.call_args[0][1])

        self.co.get_vm(name='i-VM-1')
        self.assertDictEqual({'keyword': 'i-VM-1', 'listall': True}, self.co._cs_get_single_result.call_args[0][1])

        self.co.get_vm(name='project_vm1', is_project_vm=True)
        self.assertDictEqual({'name': 'project_vm1', 'projectid': '-1', 'listall': True},
                             self.co._cs_get_single_result.call_args[0][1])

    def test_get_project_vm(self):
        self.co._cs_get_single_result = Mock()

        self.co.get_project_vm(name='project_vm1')
        self.assertDictEqual({'name': 'project_vm1', 'projectid': '-1', 'listall': True},
                             self.co._cs_get_single_result.call_args[0][1])

    def test_get_router(self):
        self.co._cs_get_single_result = Mock()

        self.co.get_router(name='router1')
        self.assertDictEqual({'name': 'router1', 'listall': True}, self.co._cs_get_single_result.call_args[0][1])

        self.co.get_router(name='project_router1', is_project_router=True)
        self.assertDictEqual({'name': 'project_router1', 'projectid': '-1', 'listall': True},
                             self.co._cs_get_single_result.call_args[0][1])

    def test_get_cluster(self):
        self.co._cs_get_single_result = Mock()
        self.co.get_zone = Mock(return_value=CosmicZone(Mock(), {'id': 'z1', 'name': 'zone1'}))

        self.co.get_cluster(name='cluster1')
        self.assertDictEqual({'name': 'cluster1'}, self.co._cs_get_single_result.call_args[0][1])

        self.co.get_cluster(name='cluster1', zone='zone1')
        self.assertDictEqual({'name': 'cluster1', 'zoneid': 'z1'}, self.co._cs_get_single_result.call_args[0][1])

        self.co.get_zone.return_value = None
        self.assertIsNone(self.co.get_cluster(name='cluster1', zone='zone1'))

    def test_get_all_clusters(self):
        self.co._cs_get_all_results = Mock()

        self.co.get_all_clusters()
        self.assertDictEqual({}, self.co._cs_get_all_results.call_args[0][1])

        self.co.get_all_clusters(zone=CosmicZone(Mock(), {'id': 'z1'}))
        self.assertDictEqual({'zoneid': 'z1'}, self.co._cs_get_all_results.call_args[0][1])

        self.co.get_all_clusters(pod=CosmicPod(Mock(), {'id': 'p1'}))
        self.assertDictEqual({'podid': 'p1'}, self.co._cs_get_all_results.call_args[0][1])

    def test_get_service_offering(self):
        self.co._cs_get_single_result = Mock()

        self.co.get_service_offering(name='so1')
        self.assertDictEqual({'name': 'so1'}, self.co._cs_get_single_result.call_args[0][1])

        self.co.get_service_offering(name='so1', system=True)
        self.assertDictEqual({'name': 'so1', 'issystem': True}, self.co._cs_get_single_result.call_args[0][1])

    def test_get_all_vms(self):
        self.co._cs_get_all_results = Mock()

        self.co.get_all_vms()
        self.assertDictEqual({'listall': True}, self.co._cs_get_all_results.call_args[0][1])

    def test_get_all_project_vms(self):
        self.co._cs_get_all_results = Mock()

        self.co.get_all_project_vms()
        self.assertDictEqual({'projectid': '-1', 'listall': True}, self.co._cs_get_all_results.call_args[0][1])

    def test_wait_for_job(self):
        self.cs_instance.queryAsyncJobResult.return_value = {'jobstatus': '1'}
        self.assertTrue(self.co.wait_for_job('job'))

    def test_wait_for_job_cloud_stack_exception(self):
        self.cs_instance.queryAsyncJobResult.side_effect = CloudStackException(response=Mock())
        self.assertRaises(CloudStackException, self.co.wait_for_job, 'job')

    def test_wait_for_job_connection_error(self):
        self.cs_instance.queryAsyncJobResult.side_effect = ConnectionError
        self.assertRaises(ConnectionError, self.co.wait_for_job, 'job')

    def test_wait_for_job_retries(self):
        self.cs_instance.queryAsyncJobResult.side_effect = [
            CloudStackException('multiple JSON fields named jobstatus', response=Mock()),
            ConnectionError('Connection aborted'),
            ConnectionError('Connection aborted')
        ]
        self.assertFalse(self.co.wait_for_job('job', 3))

    def test_wait_for_job_failure(self):
        self.cs_instance.queryAsyncJobResult.return_value = {'jobstatus': '2'}
        self.assertFalse(self.co.wait_for_job('job'))

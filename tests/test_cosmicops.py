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

    def test_get_host_by_name(self):
        self.cs_instance.listHosts.return_value = {
            'host': [{
                'id': 'h1',
                'name': 'host1',
                'clusterid': '1'
            }]
        }

        result = self.co.get_host_by_name('host1')
        self.assertEqual(('h1', 'host1', '1'), (result['id'], result['name'], result['clusterid']))

    def test_get_host_by_name_failure(self):
        self.cs_instance.listHosts.return_value = {'host': []}
        self.assertIsNone(self.co.get_host_by_name('host1'))

        self.cs_instance.listHosts.return_value = {'host': [{}, {}]}
        self.assertIsNone(self.co.get_host_by_name('host1'))

    def test_get_cluster_by_name(self):
        self.cs_instance.listClusters.return_value = {
            'cluster': [{
                'id': 'c1',
                'name': 'cluster1'
            }]
        }

        result = self.co.get_cluster_by_name('cluster1')
        self.assertEqual(('c1', 'cluster1'), (result['id'], result['name']))

    def test_get_cluster_by_name_with_zone(self):
        self.cs_instance.listZones.return_value = {
            'zone': [{
                'id': 'z1',
                'name': 'zone1'
            }]
        }

        self.co.get_cluster_by_name('cluster1', 'zone1')
        self.cs_instance.listClusters.assert_called_with(name='cluster1', zoneid='z1')

    def test_get_cluster_by_name_failure(self):
        self.cs_instance.listClusters.return_value = {'cluster': []}
        self.assertIsNone(self.co.get_cluster_by_name('cluster1'))

        self.cs_instance.listClusters.return_value = {'cluster': [{}, {}]}
        self.assertIsNone(self.co.get_cluster_by_name('cluster1'))

    def test_get_all_clusters(self):
        self.cs_instance.listClusters.return_value = {
            'cluster': [{
                'id': 'c1',
                'name': 'cluster1'
            }, {
                'id': 'c2',
                'name': 'cluster2'
            }]
        }

        result = self.co.get_all_clusters()
        self.assertEqual(('c1', 'cluster1', 'c2', 'cluster2'),
                         (result[0]['id'], result[0]['name'], result[1]['id'], result[1]['name']))

    def test_all_clusters_with_zone(self):
        self.cs_instance.listZones.return_value = {
            'zone': [{
                'id': 'z1',
                'name': 'zone1'
            }]
        }

        self.co.get_all_clusters('zone1')
        self.cs_instance.listClusters.assert_called_with(zoneid='z1')

    def test_get_all_clusters_failure(self):
        self.cs_instance.listClusters.return_value = {'cluster': []}
        self.assertIsNone(self.co.get_all_clusters())

    def test_get_systemvm_by_name(self):
        self.cs_instance.listSystemVms.return_value = {
            'systemvm': [{
                'id': 'svm1',
                'name': 's-1-VM'
            }]
        }

        result = self.co.get_systemvm_by_name('s-1-VM')
        self.assertEqual(('svm1', 's-1-VM'), (result['id'], result['name']))

    def test_get_systemvm_by_name_failure(self):
        self.cs_instance.listSystemVms.return_value = {'systemvm': []}
        self.assertIsNone(self.co.get_systemvm_by_name('s-1-VM'))

        self.cs_instance.listSystemVms.return_value = {'systemvm': [{}, {}]}
        self.assertIsNone(self.co.get_systemvm_by_name('s-1-VM'))

    def test_get_systemvm_by_id(self):
        self.cs_instance.listSystemVms.return_value = {
            'systemvm': [{
                'id': 'svm1',
                'name': 's-1-VM'
            }]
        }

        result = self.co.get_systemvm_by_id('svm1')
        self.assertEqual(('svm1', 's-1-VM'), (result['id'], result['name']))

    def test_get_systemvm_by_id_failure(self):
        self.cs_instance.listSystemVms.return_value = {'systemvm': []}
        self.assertIsNone(self.co.get_systemvm_by_id('svm1'))

        self.cs_instance.listSystemVms.return_value = {'systemvm': [{}, {}]}
        self.assertIsNone(self.co.get_systemvm_by_id('svm1'))

    def test_get_all_systemvms(self):
        self.cs_instance.listSystemVms.return_value = {
            'systemvm': [{
                'id': 'svm1',
                'name': 's-1-VM'
            }, {
                'id': 'svm2',
                'name': 's-2-VM'
            }]
        }

        result = self.co.get_all_systemvms()
        self.assertEqual(('svm1', 's-1-VM', 'svm2', 's-2-VM'),
                         (result[0]['id'], result[0]['name'], result[1]['id'], result[1]['name']))

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

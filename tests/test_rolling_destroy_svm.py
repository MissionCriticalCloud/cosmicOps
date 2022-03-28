# Copyright 2021, Schuberg Philis B.V
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
from unittest.mock import patch, Mock

from click.testing import CliRunner

import rolling_destroy_svm
from cosmicops.objects import CosmicSystemVM, CosmicHost


class TestRollingDestroySVM(TestCase):
    def setUp(self):
        co_patcher = patch('rolling_destroy_svm.CosmicOps')
        sleep_patcher = patch('time.sleep', return_value=None)
        self.co = co_patcher.start()
        sleep_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.addCleanup(sleep_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()

        self._setup_mocks()

    def _setup_mocks(self):
        self.svm1 = CosmicSystemVM(Mock(), {
            'id': 's1',
            'name': 's-1-VM',
            'zonename': 'zone1',
            'zoneid': 'ECC106A3-49EF-41E6-8A49-4C7ADF329A05',
            'hostname': 'kvm1'
        })
        self.svm1_host = CosmicHost(Mock(), {
            'id': 'sh1',
            'name': 's-1-VM',
            'version': '1.0.0',
            'state': 'Up',
            'zonename': 'zone1',
            'zoneid': 'ECC106A3-49EF-41E6-8A49-4C7ADF329A05',
            'resourcestate': 'Enabled'
        })
        self.svm2 = CosmicSystemVM(Mock(), {
            'id': 's2',
            'name': 'v-2-VM',
            'zonename': 'zone2',
            'zoneid': 'BD687FC1-F138-4B3D-929D-4695F9B6EC98',
            'hostname': 'kvm2'
        })
        self.svm2_host = CosmicHost(Mock(), {
            'id': 'sh2',
            'name': 'v-2-VM',
            'version': '2.0.0',
            'state': 'Up',
            'zonename': 'zone2',
            'zoneid': 'BD687FC1-F138-4B3D-929D-4695F9B6EC98',
            'resourcestate': 'Enabled'
        })
        self.svm3 = CosmicSystemVM(Mock(), {
            'id': 's3',
            'name': 'r-3-VM',
            'zonename': 'zone1',
            'zoneid': 'ECC106A3-49EF-41E6-8A49-4C7ADF329A05',
            'hostname': 'kvm3'
        })
        self.svm3_host = CosmicHost(Mock(), {
            'id': 'sh3',
            'name': 'r-3-VM',
            'version': '3.0.0',
            'state': 'Up',
            'zonename': 'zone1',
            'zoneid': 'ECC106A3-49EF-41E6-8A49-4C7ADF329A05',
            'resourcestate': 'Enabled'
        })

        self.all_systemvms = [self.svm1, self.svm2, self.svm3]
        self.zone1_systemvms = [svm for svm in self.all_systemvms if svm['zonename'] == 'zone1']
        self.zone2_systemvms = [svm for svm in self.all_systemvms if svm['zonename'] == 'zone2']
        self.all_hosts = [self.svm1_host, self.svm2_host, self.svm3_host]

        for svm in self.all_systemvms:
            svm.destroy = Mock(return_value=True)

        self.co_instance.get_all_systemvms.side_effect = [self.all_systemvms, self.zone1_systemvms, self.zone1_systemvms, self.zone2_systemvms]
        self.co_instance.get_host.side_effect = len(self.all_systemvms) * self.all_hosts

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(rolling_destroy_svm.main,
                                               ['--exec', '-p', 'profile']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=False)

        self.co_instance.get_all_systemvms.assert_called()
        for vm in self.all_systemvms:
            vm.destroy.assert_called()

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(rolling_destroy_svm.main,
                                               ['-p', 'profile']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=True)
        self.co_instance._ops.cs.destroySystemVm.assert_not_called()

    def test_skip_version(self):
        self.assertEqual(0, self.runner.invoke(rolling_destroy_svm.main,
                                               ['--exec', '-p', 'profile', '--skip-version', '2.0.0']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=False)

        self.co_instance.get_all_systemvms.assert_called()
        for vm in [self.svm1, self.svm3]:
            vm.destroy.assert_called()

        self.svm2.destroy.assert_not_called()

    def test_skip_zone(self):
        self.assertEqual(0, self.runner.invoke(rolling_destroy_svm.main,
                                               ['--exec', '-p', 'profile', '--skip-zone', 'zone1']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=False)

        self.co_instance.get_all_systemvms.assert_called()
        for vm in self.zone1_systemvms:
            vm.destroy.assert_not_called()

        for vm in self.zone2_systemvms:
            vm.destroy.assert_called()

    def test_failures(self):
        self.svm1.destroy.return_value = False

        self.assertEqual(1, self.runner.invoke(rolling_destroy_svm.main,
                                               ['--exec', '-p', 'profile']).exit_code)

    def test_retries(self):
        self.co_instance.get_all_systemvms.side_effect = None
        self.co_instance.get_all_systemvms.return_value = self.zone1_systemvms
        self.svm1_host['state'] = 'Disconnected'
        self.co_instance.get_host = Mock(return_value=self.svm1_host)

        self.assertEqual(1, self.runner.invoke(rolling_destroy_svm.main,
                                               ['--exec', '-p', 'profile']).exit_code)

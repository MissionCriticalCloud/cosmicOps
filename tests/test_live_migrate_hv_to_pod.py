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
from unittest.mock import patch, Mock

from click.testing import CliRunner

import live_migrate_hv_to_pod
from cosmicops.objects import CosmicCluster, CosmicHost, CosmicVM


class TestLiveMigrateHVToPod(TestCase):
    def setUp(self):
        co_patcher = patch('live_migrate_hv_to_pod.CosmicOps')
        cs_patcher = patch('live_migrate_hv_to_pod.CosmicSQL')
        lm_patcher = patch('live_migrate_hv_to_pod.live_migrate')
        sleep_patcher = patch('time.sleep', return_value=None)
        self.co = co_patcher.start()
        self.cs = cs_patcher.start()
        self.lm = lm_patcher.start()
        sleep_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.addCleanup(cs_patcher.stop)
        self.addCleanup(lm_patcher.stop)
        self.addCleanup(sleep_patcher.stop)
        self.co_instance = self.co.return_value
        self.cs_instance = self.cs.return_value
        self.runner = CliRunner()

        self.target_cluster = CosmicCluster(Mock(), {
            'id': 'tc1',
            'name': 'target_cluster'
        })
        self.vms = [
            CosmicVM(Mock(), {
                'id': 'vm1',
                'name': 'vm1'
            }),
            CosmicVM(Mock(), {
                'id': 'vm2',
                'name': 'vm2'
            })
        ]
        self.project_vms = [
            CosmicVM(Mock(), {
                'id': 'pvm1',
                'name': 'project_vm1'
            }),
            CosmicVM(Mock(), {
                'id': 'pvm2',
                'name': 'project_vm2'
            })
        ]
        self.source_host = CosmicHost(Mock(), {
            'id': 'sh1',
            'name': 'source_host',
            'clusterid': 'sc1'
        })

        self.co_instance.get_host.return_value = self.source_host
        self.source_host.get_all_vms = Mock(return_value=self.vms)
        self.source_host.get_all_project_vms = Mock(return_value=self.project_vms)

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_hv_to_pod.main,
                                               ['--exec', '-p', 'profile', 'source_host', 'target_cluster']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=False, log_to_slack=True)
        self.cs.assert_called_with(server='profile', dry_run=False)

        self.co_instance.get_host.assert_called_with(name='source_host')
        self.source_host.get_all_vms.assert_called()
        self.source_host.get_all_project_vms.assert_called()

        for vm in self.vms + self.project_vms:
            self.lm.assert_any_call(add_affinity_group=None, cluster='target_cluster', co=self.co_instance,
                                    cs=self.cs_instance, destination_dc=None, dry_run=False, is_project_vm=None,
                                    log_to_slack=True, vm=vm, zwps_to_cwps=None)

    def test_main_dry_run(self):
        self.assertEqual(0, self.runner.invoke(live_migrate_hv_to_pod.main,
                                               ['-p', 'profile', 'source_host', 'target_cluster']).exit_code)

        self.co.assert_called_with(profile='profile', dry_run=True, log_to_slack=False)
        self.cs.assert_called_with(server='profile', dry_run=True)

        self.co_instance.get_host.assert_called_with(name='source_host')
        self.source_host.get_all_vms.assert_called()
        self.source_host.get_all_project_vms.assert_called()

        for vm in self.vms + self.project_vms:
            self.lm.assert_any_call(add_affinity_group=None, cluster='target_cluster', co=self.co_instance,
                                    cs=self.cs_instance, destination_dc=None, dry_run=True, is_project_vm=None,
                                    log_to_slack=False, vm=vm, zwps_to_cwps=None)

    def test_host_not_found(self):
        self.co_instance.get_host.return_value = None

        self.assertEqual(1, self.runner.invoke(live_migrate_hv_to_pod.main,
                                               ['--exec', '-p', 'profile', 'source_host', 'target_cluster']).exit_code)

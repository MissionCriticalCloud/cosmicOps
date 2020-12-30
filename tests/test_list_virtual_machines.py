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

from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch, Mock

from click.testing import CliRunner

import list_virtual_machines
from cosmicops.objects import CosmicCluster, CosmicHost, CosmicVM, CosmicDomain, CosmicPod, CosmicZone, CosmicProject, \
    CosmicVPC, CosmicServiceOffering, CosmicNetwork, CosmicRouter


class TestListVirtualMachines(TestCase):
    def setUp(self):
        co_patcher = patch('list_virtual_machines.CosmicOps')
        self.co = co_patcher.start()
        self.addCleanup(co_patcher.stop)
        self.co_instance = self.co.return_value
        self.runner = CliRunner()

        self.cluster = CosmicCluster(Mock(), {'id': 'c1', 'name': 'cluster1'})
        self.domain = CosmicDomain(Mock(), {'id': 'd1', 'name': 'domain1'})
        self.project = CosmicProject(Mock(), {'id': 'p1', 'name': 'project1'})
        self.pod = CosmicPod(Mock(), {'id': 'p1', 'name': 'pod1'})
        self.zone = CosmicZone(Mock(), {'id': 'z1', 'name': 'zone1'})
        self.host = CosmicHost(Mock(), {
            'id': 'h1',
            'name': 'host1',
            'cpunumber': 12,
            'memorytotal': 25017704448
        })
        self.vm = CosmicVM(Mock(), {
            'id': 'v1',
            'name': 'vm1',
            'account': 'admin',
            'domain': 'ROOT',
            'cpunumber': 1,
            'memory': 512,
            'templatedisplaytext': 'tiny mock vm',
            'instancename': 'i-1-VM',
            'hostname': 'host1',
            'created': '2020-10-06T09:41:57+0200',
            'laststartversion': '6.9.2-SNAPSHOT'
        })
        self.volume = {
            'id': 'vol1',
            'name': 'ROOT-1',
            'size': 52428800
        }
        self.router = CosmicRouter(Mock(), {
            'id': 'r1',
            'name': 'router1',
            'account': 'admin',
            'domain': 'ROOT',
            'hostname': 'host1',
            'created': '2020-10-06T09:41:57+0200',
            'laststartversion': '6.9.2-SNAPSHOT',
            'isredundantrouter': False,
            'redundantstate': 'MASTER',
            'nic': [
                {'id': 'nic1'},
                {'id': 'nic2'},
                {'id': 'nic3'},
                {'id': 'nic4'}
            ],
            'vpcid': 'vpc1',
            'serviceofferingid': 'so1',
            'version': '20.3.30',
            'requiresupgrade': False
        })
        self.vpc = CosmicVPC(Mock(), {
            'id': 'vpc1',
            'name': 'vpc1'
        })
        self.network = CosmicNetwork(Mock(), {
            'id': 'net1',
            'name': 'net1'
        })
        self.service_offering = CosmicServiceOffering(Mock(), {
            'id': 'so1',
            'cpunumber': 2,
            'memory': 1024
        })
        self.cluster.get_all_hosts = Mock(return_value=[self.host])
        self.host.get_all_vms = Mock(return_value=[self.vm])
        self.host.get_all_project_vms = Mock(return_value=[])
        self.host.get_all_routers = Mock(return_value=[self.router])
        self.host.get_all_project_routers = Mock(return_value=[])
        self.vm.get_volumes = Mock(return_value=[self.volume])
        self.co_instance.get_all_clusters.return_value = [self.cluster]
        self.co_instance.get_all_vms = Mock(return_value=[self.vm])
        self.co_instance.get_all_project_vms = Mock(return_value=[])
        self.co_instance.get_cluster = Mock(return_value=self.cluster)
        self.co_instance.get_domain = Mock(return_value=self.domain)
        self.co_instance.get_project = Mock(return_value=self.project)
        self.co_instance.get_pod = Mock(return_value=self.pod)
        self.co_instance.get_zone = Mock(return_value=self.zone)
        self.co_instance.get_all_routers = Mock(return_value=[])
        self.co_instance.get_all_project_routers = Mock(return_value=[])
        self.co_instance.get_service_offering = Mock(return_value=self.service_offering)
        self.co_instance.get_vpc = Mock(return_value=self.vpc)
        self.co_instance.get_network = Mock(return_value=self.network)

    def test_main(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main).exit_code)

        self.co_instance.get_domain.assert_not_called()
        self.co_instance.get_project.assert_not_called()
        self.co_instance.get_pod.assert_not_called()
        self.co_instance.get_zone.assert_not_called()
        self.co_instance.get_all_clusters.assert_called_once()
        self.cluster.get_all_hosts.assert_called_once()
        self.host.get_all_vms.assert_called_once_with(domain=None, keyword_filter=None)
        self.vm.get_volumes.assert_called_once()

    def test_either_project_or_domain(self):
        self.assertEqual(1, self.runner.invoke(list_virtual_machines.main,
                                               ['--domain', 'domain1', '--project', 'project1']).exit_code)

    def test_calling_credentials(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--calling-credentials']).exit_code)
        self.co_instance.get_all_vms.assert_called_once_with(list_all=False)
        self.vm.get_volumes.assert_called_once()
        self.co_instance.get_all_cluster.assert_not_called()

    def test_ignore_domains(self):
        ignore_vm1 = deepcopy(self.vm)
        ignore_vm2 = deepcopy(self.vm)
        ignore_router1 = deepcopy(self.router)
        ignore_router2 = deepcopy(self.router)
        ignore_vm1['domain'] = 'ignore1'
        ignore_vm2['domain'] = 'ignore2'
        ignore_router1['domain'] = 'ignore1'
        ignore_router2['domain'] = 'ignore2'
        self.host.get_all_vms = Mock(return_value=[self.vm, ignore_vm1, ignore_vm2])
        self.host.get_all_routers = Mock(return_value=[self.router, ignore_router1, ignore_router2])
        self.co_instance.get_all_vms = Mock(return_value=[self.vm, ignore_vm1, ignore_vm2])

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main).exit_code)
        for vm in [self.vm, ignore_vm1, ignore_vm2]:
            vm.get_volumes.assert_called_once()
            vm.get_volumes.reset_mock()

        self.assertEqual(3, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--ignore-domains', 'ignore1,ignore2']).exit_code)
        self.vm.get_volumes.assert_called_once()
        self.vm.get_volumes.reset_mock()
        for vm in [ignore_vm1, ignore_vm2]:
            vm.get_volumes.assert_not_called()

        self.assertEqual(1, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--calling-credentials']).exit_code)
        for vm in [self.vm, ignore_vm1, ignore_vm2]:
            vm.get_volumes.assert_called_once()
            vm.get_volumes.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--calling-credentials', '--ignore-domains',
                                                                            'ignore1,ignore2']).exit_code)
        self.vm.get_volumes.assert_called_once()
        for vm in [ignore_vm1, ignore_vm2]:
            vm.get_volumes.assert_not_called()

    def test_only_project(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--only-project']).exit_code)
        self.host.get_all_project_vms.assert_called_once_with(project=None)
        self.host.get_all_vms.assert_not_called()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--calling-credentials', '--only-project']).exit_code)
        self.co_instance.get_all_project_vms.assert_called_once_with(list_all=False)
        self.co_instance.get_all_vms.assert_not_called()

    def test_cluster_name(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--cluster', 'cluster1']).exit_code)
        self.co_instance.get_cluster.assert_called_once_with(name='cluster1')

    def test_domain(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--domain', 'domain1']).exit_code)
        self.co_instance.get_domain.assert_called_once_with(name='domain1')
        self.host.get_all_vms.assert_called_once_with(domain=self.domain, keyword_filter=None)

    def test_project(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--project', 'project1']).exit_code)
        self.co_instance.get_project.assert_called_once_with(name='project1')
        self.host.get_all_project_vms.assert_called_once_with(project=self.project)
        self.host.get_all_vms.assert_not_called()

    def test_pod(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--pod', 'pod1']).exit_code)
        self.co_instance.get_pod.assert_called_once_with(name='pod1')
        self.co_instance.get_all_clusters.assert_called_once_with(pod=self.pod)

    def test_zone(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--zone', 'zone1']).exit_code)
        self.co_instance.get_zone.assert_called_once_with(name='zone1')
        self.co_instance.get_all_clusters.assert_called_once_with(zone=self.zone)

    def test_lookup_failures(self):
        for func in [self.co_instance.get_domain,
                     self.co_instance.get_project,
                     self.co_instance.get_pod,
                     self.co_instance.get_zone]:
            func.return_value = []

        for args in [['--domain', 'no_domain'],
                     ['--project', 'no_project'],
                     ['--pod', 'no_pod'],
                     ['--zone', 'no_zone']]:
            self.assertEqual(1, self.runner.invoke(list_virtual_machines.main, args).exit_code)

    def test_cluster_without_hosts(self):
        empty_cluster = deepcopy(self.cluster)
        empty_cluster.get_all_hosts.return_value = []
        self.co_instance.get_all_clusters.return_value = [empty_cluster, self.cluster]

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main).exit_code)

        empty_cluster.get_all_hosts.assert_called_once()
        self.cluster.get_all_hosts.assert_called_once()

    def test_router_min_version(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--router-min-version', '19.0.0']).exit_code)
        self.assertEqual(1, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--router-min-version', '21.0.0']).exit_code)
        self.assertEqual(0, self.co_instance.get_service_offering.call_count)

    def test_router_max_version(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--router-max-version', '21.0.0']).exit_code)
        self.assertEqual(1, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--router-max-version', '19.0.0']).exit_code)
        self.assertEqual(0, self.co_instance.get_service_offering.call_count)

    def test_router_nic_count(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--router-nic-count', '4']).exit_code)
        self.assertEqual(1, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--router-nic-count', '3']).exit_code)
        self.assertEqual(0, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--nic-count-is-maximum', '--router-nic-count', '3']).exit_code)
        self.assertEqual(0, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--nic-count-is-maximum', '--router-nic-count', '5']).exit_code)
        self.assertEqual(1, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--nic-count-is-minimum', '--router-nic-count', '3']).exit_code)
        self.assertEqual(1, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main,
                                               ['--nic-count-is-minimum', '--router-nic-count', '5']).exit_code)
        self.assertEqual(0, self.co_instance.get_service_offering.call_count)

    def test_no_routers(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--no-routers']).exit_code)
        self.assertEqual(0, self.co_instance.get_service_offering.call_count)

    def test_routers_to_be_upgraded(self):
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--only-routers-to-be-upgraded']).exit_code)
        self.assertEqual(0, self.co_instance.get_service_offering.call_count)
        self.co_instance.get_service_offering.reset_mock()

        self.router['requiresupgrade'] = True
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main, ['--only-routers-to-be-upgraded']).exit_code)
        self.assertEqual(1, self.co_instance.get_service_offering.call_count)

    def test_empty_service_offering(self):
        self.co_instance.get_service_offering.return_value = None
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main).exit_code)

    def test_router_redundancy_states(self):
        self.router['isredundantrouter'] = True

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main).exit_code)
        self.co_instance.get_vpc.assert_called_with(id='vpc1')
        self.co_instance.get_network.assert_not_called()
        for func in [self.co_instance.get_vpc, self.co_instance.get_network]:
            func.reset_mock()

        self.router['isredundantrouter'] = False
        self.router['vpcid'] = None
        self.router['guestnetworkid'] = 'net1'

        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main).exit_code)
        self.co_instance.get_vpc.assert_not_called()
        self.co_instance.get_network.assert_called_with(id='net1')
        for func in [self.co_instance.get_vpc, self.co_instance.get_network]:
            func.reset_mock()

        self.co_instance.get_network.return_value = None
        self.assertEqual(0, self.runner.invoke(list_virtual_machines.main).exit_code)

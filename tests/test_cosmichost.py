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
from unittest.mock import Mock, patch, call

from cosmicops import CosmicOps, CosmicHost, CosmicVM
from cosmicops.host import RebootAction


class TestCosmicHost(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.ops.CloudStack')
        self.mock_cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.mock_cs.return_value

        connection_patcher = patch('cosmicops.host.Connection')
        self.mock_connection = connection_patcher.start()
        self.addCleanup(connection_patcher.stop)
        self.connection_instance = self.mock_connection.return_value

        socket_patcher = patch('socket.socket')
        self.mock_socket = socket_patcher.start()
        self.addCleanup(socket_patcher.stop)
        self.socket_context = self.mock_socket.return_value.__enter__.return_value

        sleep_patcher = patch('time.sleep', return_value=None)
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self.ops = CosmicOps(endpoint='https://localhost', key='key', secret='secret', dry_run=False)

        self.user_vm = CosmicVM(self.ops, {
            'id': 'v1',
            'name': 'vm1',
            'instancename': 'i-1-VM',
            'hostname': 'host1',
            'maintenancepolicy': 'LiveMigrate',
            'isoid': 'iso1'
        })
        self.router_vm = CosmicVM(self.ops, {
            'id': 'r1',
            'name': 'r-1-VM',
            'hostname': 'host1'
        })
        self.secondary_storage_vm = CosmicVM(self.ops, {
            'id': 's1',
            'name': 's-1-VM',
            'hostname': 'host1',
            'systemvmtype': 'secondarystoragevm'
        })

        self.console_proxy = CosmicVM(self.ops, {
            'id': 's2',
            'name': 'v-2-VM',
            'hostname': 'host1',
            'systemvmtype': 'consoleproxy'
        })

        self.all_vms = [self.user_vm, self.router_vm, self.secondary_storage_vm, self.console_proxy]

        self.host = CosmicHost(self.ops, {
            'id': 'h1',
            'name': 'host1',
            'clusterid': '1'
        })

    def _mock_cosmic_vm_calls(self):
        self.cs_instance.listVirtualMachines.side_effect = [
            {
                'virtualmachine': [{
                    'id': 'v1',
                    'name': 'vm1',
                    'instancename': 'i-1-VM',
                    'hostname': 'host1',
                    'maintenancepolicy': 'LiveMigrate',
                    'isoid': 'iso1'
                }]
            },
            {}
        ]
        self.cs_instance.listRouters.side_effect = [
            {
                'router': [{
                    'id': 'r1',
                    'name': 'r-1-VM',
                    'hostname': 'host1'
                }]
            },
            {}
        ]
        self.cs_instance.listSystemVms.side_effect = [
            {
                'systemvm': [{
                    'id': 's1',
                    'name': 's-1-VM',
                    'hostname': 'host1',
                    'systemvmtype': 'secondarystoragevm'
                }, {
                    'id': 's2',
                    'name': 'v-2-VM',
                    'hostname': 'host1',
                    'systemvmtype': 'consoleproxy'
                }]
            },
            {}
        ]

    def _mock_hosts_and_vms(self):
        for vm in self.all_vms:
            vm.stop = Mock(return_value=True)
            vm.start = Mock(return_value=True)
            vm.get_affinity_groups = Mock(return_value=[])
            vm.migrate = Mock(return_value=True)

        self.host.get_all_vms = Mock(return_value=self.all_vms)

        self.cs_instance.findHostsForMigration.return_value = {
            'host': [{
                'id': 'host_high_mem',
                'name': 'host2',
                'memoryallocated': 1000,
                'clusterid': '1',
                'requiresStorageMotion': False,
                'suitableformigration': True
            }, {
                'id': 'host_explicit_group_2',
                'name': 'host3',
                'memoryallocated': 0,
                'clusterid': '1',
                'affinitygroupid': 'e2',
                'requiresStorageMotion': False,
                'suitableformigration': True
            }, {
                'id': 'host_explicit_group_1',
                'name': 'host4',
                'memoryallocated': 0,
                'clusterid': '1',
                'affinitygroupid': 'e1',
                'requiresStorageMotion': False,
                'suitableformigration': True
            }, {
                'id': 'host_normal',
                'name': 'host5',
                'memoryallocated': 0,
                'clusterid': '1',
                'requiresStorageMotion': False,
                'suitableformigration': True
            }]
        }

    def test_refresh(self):
        self.host.refresh()
        self.cs_instance.listHosts.assert_called_with(id='h1')

    def test_disable(self):
        def refresh_effect():
            self.host._host['resourcestate'] = 'Enabled' if self.host.refresh.call_count == 1 else 'Disabled'

        self.host.refresh = Mock(side_effect=refresh_effect)
        self.assertTrue(self.host.disable())
        self.cs_instance.updateHost.assert_called_with(id='h1', allocationstate='Disable')

    def test_disable_dry_run(self):
        self.host.dry_run = True
        self.assertTrue(self.host.disable())
        self.cs_instance.updateHost.assert_not_called()

    def test_disable_failure(self):
        self.host.refresh = Mock()
        self.cs_instance.updateHost.return_value = {}
        self.assertFalse(self.host.disable())

    def test_enable(self):
        def refresh_effect():
            self.host._host['resourcestate'] = 'Disabled' if self.host.refresh.call_count == 1 else 'Enabled'

        self.host.refresh = Mock(side_effect=refresh_effect)
        self.assertTrue(self.host.enable())
        self.cs_instance.updateHost.assert_called_with(id='h1', allocationstate='Enable')

    def test_enable_dry_run(self):
        self.host.dry_run = True
        self.assertTrue(self.host.enable())
        self.cs_instance.updateHost.assert_not_called()

    def test_enable_failure(self):
        self.host.refresh = Mock()
        self.cs_instance.updateHost.return_value = {}
        self.assertFalse(self.host.enable())

    def test_empty(self):
        self._mock_hosts_and_vms()
        self.assertEqual((4, 4, 0), self.host.empty())
        self.user_vm.stop.assert_not_called()

        for vm in self.all_vms:
            self.assertEqual('host_normal', vm.migrate.call_args[0][0]['id'])

    def test_empty_dry_run(self):
        self.host._ops.dry_run = True
        self.host.dry_run = True
        self._mock_hosts_and_vms()

        self.assertEqual((4, 4, 0), self.host.empty())
        self.cs_instance.stopVirtualMachine.assert_not_called()
        self.cs_instance.detachIso.assert_not_called()
        self.cs_instance.migrateVirtualMachine.assert_not_called()
        self.cs_instance.migrateSystemVm.assert_not_called()

    def test_empty_on_empty_host(self):
        self.host.get_all_vms = Mock(return_value=None)
        self.assertEqual((0, 0, 0), self.host.empty())

    def test_empty_with_shutdown_and_start_policy(self):
        self.user_vm._vm['maintenancepolicy'] = 'ShutdownAndStart'
        self._mock_hosts_and_vms()

        self.assertEqual((4, 4, 0), self.host.empty())
        self.user_vm.stop.assert_called_once()
        self.assertEqual('v1', self.host.vms_with_shutdown_policy[0]['id'])

    def test_empty_with_shutdown_and_start_policy_and_failed_shutdown(self):
        self.user_vm._vm['maintenancepolicy'] = 'ShutdownAndStart'
        self._mock_hosts_and_vms()
        self.user_vm.stop.return_value = False

        self.assertEqual((4, 3, 1), self.host.empty())

        self.user_vm.stop.assert_called_once()
        self.assertEqual('v1', self.host.vms_with_shutdown_policy[0]['id'])

    def test_empty_with_affinity_group(self):
        self._mock_hosts_and_vms()
        self.user_vm.get_affinity_groups.return_value = [{
            'id': 'e1',
            'name': 'explicit1',
            'type': 'ExplicitDedication',
            'virtualmachineIds': ['v1']
        }]

        self.assertEqual((4, 4, 0), self.host.empty())
        self.assertEqual('host_explicit_group_1', self.user_vm.migrate.call_args[0][0]['id'])

    def test_empty_with_requires_storage_motion(self):
        self._mock_hosts_and_vms()
        self.cs_instance.findHostsForMigration.return_value = {
            'host': [{
                'id': 'h2',
                'name': 'host2',
                'memoryallocated': 0,
                'clusterid': '1',
                'requiresStorageMotion': True,
                'suitableformigration': True,
            }, {
                'id': 'h3',
                'name': 'host3',
                'memoryallocated': 0,
                'clusterid': '1',
                'requiresStorageMotion': False,
                'suitableformigration': True,
            }]
        }

        self.assertEqual((4, 4, 0), self.host.empty())
        self.assertEqual('h3', self.user_vm.migrate.call_args[0][0]['id'])

    def test_empty_with_different_cluster(self):
        self._mock_hosts_and_vms()
        self.cs_instance.findHostsForMigration.return_value = {
            'host': [{
                'id': 'h2',
                'name': 'host2',
                'memoryallocated': 0,
                'clusterid': '2',
                'requiresStorageMotion': False,
                'suitableformigration': True,
            }, {
                'id': 'h3',
                'name': 'host3',
                'memoryallocated': 0,
                'clusterid': '1',
                'requiresStorageMotion': False,
                'suitableformigration': True,
            }]
        }

        self.assertEqual((4, 4, 0), self.host.empty())
        self.assertEqual('h3', self.user_vm.migrate.call_args[0][0]['id'])

    def test_empty_with_unsuitable_host(self):
        self._mock_hosts_and_vms()
        self.cs_instance.findHostsForMigration.return_value = {
            'host': [{
                'id': 'h2',
                'name': 'host2',
                'memoryallocated': 0,
                'clusterid': '1',
                'requiresStorageMotion': False,
                'suitableformigration': False,
            }, {
                'id': 'h3',
                'name': 'host3',
                'memoryallocated': 0,
                'clusterid': '1',
                'requiresStorageMotion': False,
                'suitableformigration': True,
            }]
        }

        self.assertEqual((4, 4, 0), self.host.empty())
        self.assertEqual('h3', self.user_vm.migrate.call_args[0][0]['id'])

    def test_empty_without_migration_host(self):
        self._mock_hosts_and_vms()
        self.cs_instance.findHostsForMigration.return_value = {}

        self.assertEqual((4, 0, 4), self.host.empty())
        self.assertEqual(4, self.cs_instance.findHostsForMigration.call_count)

        for vm in self.all_vms:
            vm.migrate.assert_not_called()

    def test_empty_with_migrate_virtual_machine_failure(self):
        self._mock_hosts_and_vms()
        self.user_vm.migrate.return_value = False
        self.assertEqual((4, 3, 1), self.host.empty())

    def test_empty_with_migrate_system_vm_failure(self):
        self._mock_hosts_and_vms()
        self.secondary_storage_vm.migrate.return_value = False
        self.console_proxy.migrate.return_value = False
        self.assertEqual((4, 2, 2), self.host.empty())

    def test_get_all_vms(self):
        self._mock_cosmic_vm_calls()
        self.host.get_all_vms()

        self.cs_instance.listVirtualMachines.assert_has_calls([call(hostid='h1', listall='true'),
                                                               call(hostid='h1', listall='true', projectid='-1')], True)
        self.cs_instance.listRouters.assert_has_calls([call(hostid='h1', listall='true'),
                                                       call(hostid='h1', listall='true', projectid='-1')], True)
        self.cs_instance.listSystemVms.assert_called_with(hostid='h1')

    def test_copy_file(self):
        self.host.copy_file('src', 'dst')
        self.connection_instance.put.assert_called_with('src', 'dst')

        self.host.copy_file('src', 'dst', 0o644)
        self.connection_instance.sudo.assert_called_with('chmod 644 dst')

    def test_copy_file_dry_run(self):
        self.host.dry_run = True

        self.host.copy_file('src', 'dst')
        self.connection_instance.put.assert_not_called()

    def test_execute(self):
        self.host.execute('cmd')
        self.connection_instance.run.assert_called_with('cmd')

        self.host.execute('cmd', True)
        self.connection_instance.sudo.assert_called_with('cmd')

    def test_execute_dry_run(self):
        self.host.dry_run = True

        self.host.execute('cmd')
        self.connection_instance.run.assert_not_called()
        self.connection_instance.sudo.assert_not_called()

    def test_reboot(self):
        self.host.execute = Mock()
        self.host.execute.return_value.stdout = '0\n'

        self.assertTrue(self.host.reboot())
        self.host.execute.assert_called_with('shutdown -r 1', sudo=True)
        self.assertTrue(self.host.reboot(RebootAction.HALT))
        self.host.execute.assert_called_with('shutdown -h 1', sudo=True)
        self.assertTrue(self.host.reboot(RebootAction.FORCE_RESET))
        self.host.execute.assert_has_calls([call('sync', sudo=True), call('echo b > /proc/sysrq-trigger', sudo=True)])
        self.assertTrue(self.host.reboot(RebootAction.UPGRADE_FIRMWARE))
        self.host.execute.assert_called_with("tmux new -d 'yes | sudo /usr/sbin/smartupdate upgrade && sudo reboot'")
        self.assertTrue(self.host.reboot(RebootAction.SKIP))
        self.host.execute.assert_called_with('virsh list | grep running | wc -l')

    def test_reboot_with_running_vms(self):
        self.host.execute = Mock()
        self.host.execute.return_value.stdout = '3\n'

        self.assertFalse(self.host.reboot())

    def test_reboot_exception(self):
        self.host.execute = Mock()
        self.host.execute.side_effect = [Mock(stdout='0\n'), Exception]
        self.assertTrue(self.host.reboot())

    def test_reboot_dry_run(self):
        self.host.dry_run = True
        self.host.execute = Mock()

        self.assertTrue(self.host.reboot())
        self.host.execute.assert_not_called()

    def test_wait_until_offline(self):
        self.socket_context.connect_ex.side_effect = [0, 1]

        self.host.wait_until_offline()
        self.socket_context.connect_ex.assert_called_with(('host1', 22))

    def test_wait_until_offline_dry_run(self):
        self.host.dry_run = True

        self.host.wait_until_offline()
        self.socket_context.connect_ex.assert_not_called()

    def test_wait_until_online(self):
        self.host.execute = Mock()
        self.host.execute.side_effect = [Mock(return_code=1), Mock(return_code=0)]
        self.socket_context.connect_ex.side_effect = [1, 0]

        self.host.wait_until_online()
        self.socket_context.connect_ex.assert_called_with(('host1', 22))
        self.host.execute.assert_called_with('virsh list')

    def test_wait_until_online_dry_run(self):
        self.host.dry_run = True
        self.host.execute = Mock()

        self.host.wait_until_online()
        self.socket_context.connect_ex.assert_not_called()
        self.host.execute.assert_not_called()

    def test_wait_for_agent(self):
        def refresh_effect():
            self.host._host['state'] = 'Disconnected' if self.host.refresh.call_count == 1 else 'Up'

        self.host.refresh = Mock(side_effect=refresh_effect)

        self.host.wait_for_agent()
        self.assertEqual(2, self.host.refresh.call_count)

    def test_wait_for_agent_dry_run(self):
        self.host.dry_run = True
        self.host.refresh = Mock()

        self.host.wait_for_agent()
        self.host.refresh.assert_not_called()

    def _mock_vms_with_shutdown_policy(self):
        self.host.vms_with_shutdown_policy = [
            CosmicVM(self.ops, {'id': 'vm1', 'name': 'vm1'}),
            CosmicVM(self.ops, {'id': 'vm2', 'name': 'vm2'})
        ]
        self.host._ops.wait_for_job = Mock(side_effect=[False, True])

    def test_restart_vms_with_shutdown_policy(self):
        self._mock_vms_with_shutdown_policy()

        self.host.restart_vms_with_shutdown_policy()
        self.cs_instance.startVirtualMachine.assert_has_calls([call(id='vm1'), call(id='vm2')], True)

    def test_restart_vms_with_shutdown_policy_dry_run(self):
        self.host._ops.dry_run = True
        self.host.dry_run = True
        self._mock_vms_with_shutdown_policy()

        self.host.restart_vms_with_shutdown_policy()
        self.cs_instance.startVirtualMachine.assert_not_called()

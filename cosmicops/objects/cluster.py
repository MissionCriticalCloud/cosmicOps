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
from operator import itemgetter

from cosmicops.log import logging
from .host import CosmicHost
from .object import CosmicObject
from .storagepool import CosmicStoragePool


class CosmicCluster(CosmicObject):
    def get_all_hosts(self):
        return [CosmicHost(self._ops, host) for host in
                self._ops.cs.listHosts(fetch_list=True, clusterid=self['id'], listall='true')]

    def get_storage_pools(self):
        storage_pools = self._ops.cs.listStoragePools(fetch_list=True, clusterid=self['id'], listall='true')

        return [CosmicStoragePool(self._ops, storage_pool) for storage_pool in storage_pools]

    def find_migration_host(self, vm):
        hosts = self.get_all_hosts()

        hosts.sort(key=itemgetter('memoryallocated'))

        migration_host = None

        for host in hosts:
            if host['name'] == vm['hostname']:
                continue

            if host['resourcestate'] != 'Enabled':
                continue

            if host['state'] != 'Up':
                continue

            available_memory = host['memorytotal'] - host['memoryallocated']
            available_memory /= 1048576

            if 'instancename' not in vm:
                service_offering = self._ops.get_service_offering(id=vm['serviceofferingid'], system=True)
                if service_offering:
                    vm['memory'] = service_offering['memory']
                else:
                    vm['memory'] = 1024

            if available_memory < vm['memory']:
                logging.warning(f"Skipping '{host['name']}' as it does not have enough memory available")
                continue

            migration_host = host
            break

        return migration_host

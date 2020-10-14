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
from collections.abc import Mapping

from .host import CosmicHost
from .storagepool import CosmicStoragePool


class CosmicCluster(Mapping):
    def __init__(self, ops, cluster):
        self._ops = ops
        self._cluster = cluster

    def __getitem__(self, item):
        return self._cluster[item]

    def __iter__(self):
        return iter(self._cluster)

    def __len__(self):
        return len(self._cluster)

    def get_all_hosts(self):
        return [CosmicHost(self._ops, host) for host in
                self._ops.cs.listHosts(clusterid=self['id'], listall='true').get('host', [])]

    def get_storage_pools(self):
        storage_pools = self._ops.cs.listStoragePools(clusterid=self['id'], listall='true').get('storagepool', [])

        return [CosmicStoragePool(self._ops, storage_pool) for storage_pool in storage_pools]

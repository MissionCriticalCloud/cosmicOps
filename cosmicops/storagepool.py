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


class CosmicStoragePool(Mapping):
    def __init__(self, ops, storage_pool):
        self._ops = ops
        self._storage_pool = storage_pool

    def __getitem__(self, item):
        return self._storage_pool[item]

    def __iter__(self):
        return iter(self._storage_pool)

    def __len__(self):
        return len(self._storage_pool)

    def get_orphaned_volumes(self):
        volumes = self._ops.cs.listVolumes(storageid=self['id']).get('volume', [])

        return [volume for volume in volumes if not volume.get('vmname')]

    def get_file_list(self, host):
        file_list = {}
        device_path = f"{self['ipaddress']}:{self['path'].rstrip('/')}"

        mount_info = host.execute(
            f"cat /proc/mounts | grep \"{device_path}\"").stdout.rstrip().split()

        if mount_info:
            mount_point = mount_info[1].rstrip('/')
            output = host.execute(
                f"find -H {mount_point} -type f -exec du -sm {{}} \\;").stdout.rstrip().split('\n')

            for line in output:
                (file_size, file_path) = line.split()
                file_path = file_path.split('/')[-1].split('.')[:1][0]
                file_list[file_path] = file_size

        return file_list

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

from cosmicops.object import CosmicObject
from cosmicops.volume import CosmicVolume


class CosmicStoragePool(CosmicObject):
    def get_volumes(self, only_project=False):
        project_id = '-1' if only_project else None

        volumes = self._ops.cs.listVolumes(fetch_list=True, storageid=self['id'], projectid=project_id,
                                           listall=True)

        return [CosmicVolume(self._ops, volume) for volume in volumes]

    def get_orphaned_volumes(self):
        volumes = self.get_volumes()

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

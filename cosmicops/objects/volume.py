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
from cosmicops.log import logging
from .object import CosmicObject


class CosmicVolume(CosmicObject):
    def refresh(self):
        self._data = self._ops.get_volume(id=self['id'], json=True)

    def migrate(self, storage_pool, live_migrate=False):
        if self.dry_run:
            logging.info(
                f"Would {'live ' if live_migrate else ''}migrate volume '{self['name']}' to '{storage_pool['name']}'")
            return True

        migrate_result = self._ops.cs.migrateVolume(volumeid=self['id'], storageid=storage_pool['id'],
                                                    livemigrate=live_migrate)

        if not self._ops.wait_for_volume_job(self['id']):
            logging.error(f"Migration job '{migrate_result['jobid']}' failed")
            return False

        logging.debug(f"Migration job '{migrate_result['jobid']}' completed")

        logging.info(f"Successfully migrated volume '{self['name']}' to '{storage_pool['name']}'")
        return True

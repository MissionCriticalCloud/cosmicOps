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

from .object import CosmicObject
from cosmicops.log import logging


class CosmicAccount(CosmicObject):
    def disable(self):
        if self.dry_run:
            logging.info(f"Would disable account '{self['domain']}/{self['name']}'")
            return True
        else:
            logging.info(f"Disabling account '{self['domain']}/{self['name']}'")
        disable_response = self._ops.cs.disableAccount(id=self['id'], lock=False)
        if not self._ops.wait_for_job(disable_response['jobid']):
            logging.error(f"Failed to disable account '{self['domain']}/{self['name']}'")
            return False
        return True

    def is_enabled(self):
        return str(self['state']).lower() == 'enabled'

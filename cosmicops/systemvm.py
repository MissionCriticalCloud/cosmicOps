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

from .log import logging
from .object import CosmicObject


class CosmicSystemVM(CosmicObject):
    def stop(self):
        if self.dry_run:
            logging.info(
                f"Would shut down system VM '{self['name']}' on host '{self['hostname']}'")
            return True

        logging.info(f"Stopping system VM '{self['name']}'")
        response = self._ops.cs.stopSystemVm(id=self['id'])
        if not self._ops.wait_for_job(response['jobid']):
            logging.error(f"Failed to shutdown system VM '{self['name']}' on host '{self['hostname']}'")
            return False

        return True

    def start(self):
        if self.dry_run:
            logging.info(f"Would start system VM '{self['name']}")
            return True

        logging.info(f"Starting system VM '{self['name']}'")
        response = self._ops.cs.startSystemVm(id=self['id'])
        if not self._ops.wait_for_job(response['jobid']):
            logging.error(f"Failed to start system VM '{self['name']}'")
            return False

        return True

    def destroy(self):
        if self.dry_run:
            logging.info(f"Would destroy system VM '{self['name']}'")
            return True

        logging.info(f"Destroying system VM '{self['name']}'")
        response = self._ops.cs.destroySystemVm(id=self['id'])
        if not self._ops.wait_for_job(response['jobid']):
            logging.error(f"Failed to destroy system VM '{self['name']}'")
            return False

        return True

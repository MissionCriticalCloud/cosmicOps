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
from .vm import CosmicVM


class CosmicRouter(CosmicVM):
    def reboot(self):
        if self.dry_run:
            logging.info(f"Would reboot router '{self['name']}")
            return True

        logging.info(f"Rebooting router '{self['name']}'", self.log_to_slack)

        response = self._ops.cs.rebootRouter(id=self['id'])
        if not self._ops.wait_for_job(response['jobid']):
            logging.error(f"Failed to reboot router '{self['name']}'")
            return False

        return True

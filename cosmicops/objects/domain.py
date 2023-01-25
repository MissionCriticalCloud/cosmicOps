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
from .resourcetype import CosmicResourceType
from .object import CosmicObject
from cosmicops.log import logging


class CosmicDomain(CosmicObject):
    def delete(self, cleanup=False):
        if self.dry_run:
            logging.info(f"Would delete domain '{self['name']}'")
            return True
        else:
            logging.info(f"Deleting domain '{self['name']}'")
        delete_response = self._ops.cs.deleteDomain(id=self['id'], cleanup=cleanup)
        if not self._ops.wait_for_job(delete_response['jobid']):
            logging.error(f"Failed to delete domain '{self['name']}'")
            return False
        return True

    def get_resourcecount(self):
        response = {}
        resource_response = self._ops.cs.updateResourceCount(domainid=self['id'])
        for resource in resource_response['resourcecount']:
            response[CosmicResourceType(int(resource['resourcetype'])).name] = resource['resourcecount']

        return response

    def is_active(self):
        return str(self['state']).lower() == 'active'

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
import time

from cosmicops.log import logging
from .vm import CosmicVM
from cosmicops import get_config

import paramiko
from fabric import Connection


class CosmicSystemVM(CosmicVM):
    def __init__(self, ops, data):
        super(CosmicSystemVM, self).__init__(ops, data)

        # Load configuration
        config = get_config()
        ssh_user = config.get('ssh', 'user', fallback=None)
        ssh_key_file = config.get('ssh', 'ssh_key_file', fallback=None)
        connect_kwargs = {'banner_timeout': 60}
        if ssh_key_file:
            connect_kwargs['key_filename'] = ssh_key_file

        # Setup SSH connection
        self._connection = Connection(self['hostname'], user=ssh_user,
                                      connect_kwargs=connect_kwargs,
                                      forward_agent=True, connect_timeout=60)

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

    def start(self, host=None):
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

    def restart_agent(self):
        if self.dry_run:
            logging.info(f"Would restart agent on system VM '{self['name']}'")
            return True
        logging.info(f"Restarting agent on system VM '{self['name']}'")
        try:
            self._connection.sudo(f"ssh {self['linklocalip']} 'systemctl restart cosmic-agent'")
            time.sleep(10)
        except (paramiko.ssh_exception.SSHException, Exception):
            pass  # Ignore Exception

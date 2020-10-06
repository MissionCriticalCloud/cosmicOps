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

import logging
from configparser import ConfigParser, NoOptionError
from pathlib import Path

import pymysql

from .log import logging


class CosmicSQL(object):
    def __init__(self, server, port=3306, password=None, user='cloud', database='cloud', dry_run=True):
        self.server = server
        self.port = port
        self.user = user
        self.database = database
        self.password = password
        self.dry_run = dry_run
        self.conn = None

        self._connect()

    def _connect(self):
        if not self.password:
            config_file = Path.cwd() / 'config'
            config = ConfigParser()
            config.read(str(config_file))
            logging.debug(f"Loading SQL server details for '{self.server}' from '{config_file}'")

            if self.server not in config:
                logging.error(f"Could not find configuration section for '{self.server}' in '{config_file}'")
                raise RuntimeError

            try:
                self.password = config.get(self.server, 'password')
                self.user = config.get(self.server, 'user', fallback=self.user)
                self.port = config.getint(self.server, 'port', fallback=self.port)
                self.database = config.get(self.server, 'database', fallback=self.database)
                self.server = config.get(self.server, 'host', fallback=self.server)
            except NoOptionError as e:
                logging.error(f"Unable to read details from '{config_file}' for '{self.server}': {e}")
                raise

        try:
            self.conn = pymysql.connect(host=self.server, port=self.port, user=self.user, password=self.password,
                                        database=self.database)
        except pymysql.Error as e:
            logging.error(f"Error connecting to server '{self.server}': {e}")
            raise

        self.conn.autocommit = False

    def kill_jobs_of_instance(self, instance_id):
        cursor = self.conn.cursor()

        try:
            queries = [
                'DELETE FROM `async_job` WHERE `instance_id` = %s',
                'DELETE FROM `vm_work_job` WHERE `vm_instance_id` = %s',
                'DELETE FROM `sync_queue` WHERE `sync_objid` = %s'
            ]

            for query in queries:
                cursor.execute(query, (instance_id,))
                if self.dry_run:
                    logging.info(f'Would have executed: {query % (instance_id,)}')
                else:
                    self.conn.commit()
        except pymysql.Error as e:
            logging.error(f'Error while executing query "{query % (instance_id,)}": {e}')
            return False
        finally:
            cursor.close()

        return True

    def list_ha_workers(self, hostname=''):
        cursor = self.conn.cursor()

        if hostname:
            host_query = "AND host.name LIKE '%s%%'" % hostname
        else:
            host_query = ''

        query = f"""
        SELECT d.name AS domain,
               vm.name AS vmname,
               ha.type,
               vm.state,
               ha.created,
               ha.taken,
               ha.step,
               host.name AS hypervisor,
               ms.name AS mgtname,
               ha.state
        FROM cloud.op_ha_work ha
        LEFT JOIN cloud.mshost ms ON ms.msid = ha.mgmt_server_id
        LEFT JOIN cloud.vm_instance vm ON vm.id = ha.instance_id
        LEFT JOIN cloud.host ON host.id = ha.host_id
        LEFT JOIN cloud.domain d ON vm.domain_id = d.id
        WHERE ha.created > DATE_SUB(NOW(), INTERVAL 1 DAY) {host_query}
        GROUP BY vm.name
        ORDER BY domain, ha.created DESC
        """

        try:
            logging.debug(query)
            cursor.execute(query)

            result = cursor.fetchall()
            return result
        except pymysql.Error as e:
            logging.error(f'Error while executing query "{query}": {e}')
            raise
        finally:
            cursor.close()

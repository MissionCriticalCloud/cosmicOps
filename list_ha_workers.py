#!/usr/bin/env python3
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

import click
import click_log

from cosmicops import logging
from cosmicops.list_ha_workers import list_ha_workers


@click.command()
@click.option('--database-server', '-s', metavar='<address>', required=True,
              help='Address or alias of Cosmic database server')
@click.option('--database-name', metavar='<database>', default='cloud', show_default=True, help='Name of the database')
@click.option('--database-port', metavar='<port>', default=3306, show_default=True,
              help='Port number of the database server')
@click.option('--database-user', '-u', metavar='<user>', default='cloud', show_default=True,
              help='Username of database account')
@click.option('--database-password', '-p', metavar='<password>', help='Password of the database user')
@click.option('--hostname', '-n', metavar='<hostname>', default='', help='Show only works on this host')
@click.option('--name-filter', metavar='<vm name>', help='Filter on specified VM name')
@click.option('--non-running', is_flag=True, help='Only show entries with a non-running state')
@click.option('--plain-display', is_flag=True, help='Plain text output, no pretty tables')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
def main(database_server, database_name, database_port, database_user, database_password, hostname, name_filter,
         non_running, plain_display):
    """Lists HA workers"""

    click_log.basic_config()

    logging.info(list_ha_workers(database_server, database_name, database_port, database_user, database_password,
                                 hostname, name_filter, non_running, plain_display))


if __name__ == '__main__':
    main()

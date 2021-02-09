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
import sys

import click
import click_log

from cosmicops import logging
from cosmicops.who_has_this_ip import who_has_this_ip


@click.command()
@click.option('--database-server', '-s', metavar='<address>',
              help='Address or alias of Cosmic database server')
@click.option('--all-databases', '-a', is_flag=True, help='Search through all configured databases')
@click.option('--database-name', metavar='<database>', default='cloud', show_default=True, help='Name of the database')
@click.option('--database-port', metavar='<port>', default=3306, show_default=True,
              help='Port number of the database server')
@click.option('--database-user', '-u', metavar='<user>', default='cloud', show_default=True,
              help='Username of database account')
@click.option('--database-password', '-p', metavar='<password>', help='Password of the database user')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('ip_address')
def main(database_server, all_databases, database_name, database_port, database_user, database_password, ip_address):
    """Shows who uses IP_ADDRESS"""

    click_log.basic_config()

    if not (database_server or all_databases):
        logging.error("You must specify --database-server or --all-databases")
        sys.exit(1)

    if database_server and all_databases:
        logging.error("The --database-server and --all-databases options can't be used together")
        sys.exit(1)

    try:
        result = who_has_this_ip(database_server, all_databases, database_name, database_port, database_user,
                                 database_password, ip_address)
    except RuntimeError as err:
        logging.error(err)
        sys.exit(1)

    logging.info(result)


if __name__ == '__main__':
    main()

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
from tabulate import tabulate

from cosmicops import CosmicSQL, logging


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
@click.argument('mac_address')
def main(database_server, all_databases, database_name, database_port, database_user, database_password, mac_address):
    """Shows who uses MAC_ADDRESS"""

    click_log.basic_config()

    if not (database_server or all_databases):
        logging.error("You must specify --database-server or --all-databases")
        sys.exit(1)

    if database_server and all_databases:
        logging.error("The --database-server and --all-databases options can't be used together")
        sys.exit(1)

    if all_databases:
        databases = CosmicSQL.get_all_dbs_from_config()
        if not databases:
            logging.error("No databases found in configuration file")
            sys.exit(1)
    else:
        databases = [database_server]

    table_headers = [
        "VM",
        "Network",
        "MAC address",
        "IPv4",
        "Netmask",
        "Mode",
        "State",
        "Created"
    ]
    table_data = []

    for database in databases:
        cs = CosmicSQL(server=database, database=database_name, port=database_port, user=database_user,
                       password=database_password,
                       dry_run=False)

        count = 0

        for (
                network_name, mac_address, ipv4_address, netmask, _, mode, state, created,
                vm_name) in cs.get_mac_address_data(
            mac_address):
            count += 1
            table_data.append([vm_name, network_name, mac_address, ipv4_address, netmask, mode, state, created])

    logging.info(tabulate(table_data, headers=table_headers, tablefmt='pretty'))


if __name__ == '__main__':
    main()

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

import logging

import click
import click_log

from cosmicops import CosmicSQL


@click.command()
@click.option('--database-server', '-s', metavar='<address>', required=True,
              help='Address or alias of Cosmic database server')
@click.option('--database-name', metavar='<database>', default='cloud', show_default=True, help='Name of the database')
@click.option('--database-port', metavar='<port>', default=3306, show_default=True,
              help='Port number of the database server')
@click.option('--database-user', '-u', metavar='<user>', default='cloud', show_default=True,
              help='Username of database account')
@click.option('--database-password', '-p', metavar='<password>', help='Password of the database user')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('instance_id')
def main(database_server, database_name, database_port, database_user, database_password, dry_run, instance_id):
    """Kills all jobs related to INSTANCE_ID"""

    click_log.basic_config()

    if dry_run:
        logging.warning('Running in dry-run mode, will only show changes')

    cs = CosmicSQL(server=database_server, database=database_name, port=database_port, user=database_user,
                   password=database_password,
                   dry_run=dry_run)

    cs.kill_jobs_of_instance(instance_id)


if __name__ == '__main__':
    main()

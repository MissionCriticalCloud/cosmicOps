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
from cosmicops.empty_host import empty_host


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--shutdown', is_flag=True, help='Shutdown host when all VMs have been migrated')
@click.option('--skip-disable', is_flag=True, help='Do not disable host before emptying it')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('host')
@click.option('--target-host', help='Target hypervisor the migrate VMS to', required=False)
def main(profile, shutdown, skip_disable, dry_run, host, target_host):
    """Empty HOST by migrating VMs to another host in the same cluster."""

    click_log.basic_config()

    if dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    try:
        logging.info(empty_host(profile, shutdown, skip_disable, dry_run, host, target_host))
    except RuntimeError as err:
        logging.error(err)
        sys.exit(1)


if __name__ == '__main__':
    main()

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
import sys

import click
import click_log

from cosmicops import CosmicOps


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('host')
def main(profile, dry_run, host):
    """Empty HOST by migrating VMs to another host in the same cluster."""

    click_log.basic_config()

    if dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run)

    host = co.get_host_by_name(host)
    if not host:
        sys.exit(1)

    (total, success, failed) = host.empty()
    logging.info(f"Result: {success} successful, {failed} failed out of {total} total VMs")


if __name__ == '__main__':
    main()

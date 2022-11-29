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
import re

import click
import click_log

from cosmicops import logging, CosmicOps
from cosmicops.objects import CosmicResourceType


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--skip-name', metavar='<skip_name>', default=None, help='Skips name (regex)')
@click.option('--delete-domain', is_flag=True, default=False, show_default=True, help='Delete domain')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
def main(profile, skip_name, delete_domain, dry_run):
    """Cleanup empty tenants"""

    click_log.basic_config()
    if dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    logging.info('Getting all accounts...\n\n')

    regex = None
    if skip_name:
        regex = re.compile(skip_name)
    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=False, timeout=300)
    accounts = co.get_all_accounts()

    # Disable accounts with no VM's
    print("=== Accounts with no VM's ===\n")
    for account in accounts:
        if account['domain'] == 'ROOT' or (regex and regex.match(account['name'])):
            continue
        domain = co.get_domain(id=account['domainid'])
        if domain.is_active() and account.is_enabled():
            resources = domain.get_resourcecount()
            if resources[CosmicResourceType.VMS.name] == 0:
                if delete_domain:
                    domain.delete()
                elif account.is_enabled():
                    account.disable()
                    if resources[CosmicResourceType.VPCS.name] > 0:
                        if dry_run:
                            logging.info(f"  We would stop the running VPCs for this domain, if any")
                        else:
                            logging.info(f"  We will stop the running VPCs for this domain, if any")
    sys.exit(0)


if __name__ == '__main__':
    main()

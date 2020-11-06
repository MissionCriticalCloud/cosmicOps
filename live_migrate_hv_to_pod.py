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

from cosmicops import CosmicOps, logging


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--destination-dc', '-d', metavar='<DC name>', help='Name of the datacenter to migrate to')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('host')
@click.argument('cluster')
def main(profile, destination_dc, dry_run, host, cluster):
    """Empty/migrate HOST to CLUSTER."""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Live Migrate HV to new POD'
    logging.slack_title = 'Domain'
    logging.slack_value = ''

    if dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    host = co.get_host_by_name(host)
    if not host:
        sys.exit(1)

    # Get list of VMs
    # Get list of project VMs
    # Loop through VMs
    # TODO: Depends on live_migrate_virtual_machine for migration
    # lmvm.liveMigrateVirtualMachine(c, DEBUG, DRYRUN, vm['instancename'], toCluster, configProfileName, isProjectVm (0 or 1), force, zwps2cwps (False), destination_dc_name, affinityGroupToAdd (''), multirun=True)
    # Count remaining VMs
    # If higher than 0 report failure


if __name__ == '__main__':
    main()

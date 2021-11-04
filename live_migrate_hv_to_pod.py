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

from cosmicops import CosmicOps, logging, CosmicSQL
from live_migrate_virtual_machine import live_migrate


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--destination-dc', '-d', metavar='<DC name>', help='Migrate to this datacenter')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('host')
@click.argument('cluster')
def main(profile, destination_dc, dry_run, host, cluster):
    """Migrate all VMs on HOST to CLUSTER"""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Live Migrate HV to new POD'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    cs = CosmicSQL(server=profile, dry_run=dry_run)

    host = co.get_host(name=host)
    if not host:
        sys.exit(1)

    for vm in host.get_all_vms() + host.get_all_project_vms():
        live_migrate(co=co, cs=cs, cluster=cluster, vm_name=vm['name'], destination_dc=destination_dc,
                     add_affinity_group=None, is_project_vm=None, zwps_to_cwps=None, log_to_slack=log_to_slack,
                     dry_run=dry_run)


if __name__ == '__main__':
    main()

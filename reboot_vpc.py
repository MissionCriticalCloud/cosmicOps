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
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--uuid', '-u', is_flag=True, help='Lookup VPC by UUID')
@click.option('--network-uuid', '-t', is_flag=True, help='Lookup VPC by VPC Tier UUID')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vpc')
def main(profile, uuid, network_uuid, dry_run, vpc):
    """VPC restart script"""

    click_log.basic_config()

    log_to_slack = True

    if uuid and network_uuid:
        logging.error('You can not specify --uuid and --network-uuid together')
        sys.exit(1)

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    if uuid:
        vpc = co.get_vpc(id=vpc)
    elif network_uuid:
        network = co.get_network(id=vpc)
        if not network:
            sys.exit(1)

        vpc = co.get_vpc(id=network['vpcid'])
    else:
        vpc = co.get_vpc(name=vpc)

    if not vpc:
        sys.exit(1)

    logging.slack_title = 'Domain'
    logging.slack_value = vpc['domain']
    logging.instance_name = vpc['name']
    logging.zone_name = vpc['zonename']

    if not vpc.restart():
        sys.exit(1)

    logging.info(f"Successfully restarted VPC '{vpc['name']}' ({vpc['id']}) with clean up")


if __name__ == '__main__':
    main()

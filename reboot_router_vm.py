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
@click.option('--is-project-router', is_flag=True, help='The specified router belongs to a project')
@click.option('--only-when-required', is_flag=True, help='Only reboot when an upgrade is required')
@click.option('--cleanup', is_flag=True, help='Restart with cleanup')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('router')
def main(profile, is_project_router, only_when_required, cleanup, dry_run, router):
    """Router restart and upgrade script"""

    click_log.basic_config()

    log_to_slack = True

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    router = co.get_router(name=router, is_project_router=is_project_router)
    if not router:
        sys.exit(1)

    logging.instance_name = router['name']
    logging.slack_title = 'Domain'
    logging.slack_value = router['domain']

    host = co.get_host(id=router['hostid'])
    if not host:
        sys.exit(1)

    cluster = co.get_cluster(id=host['clusterid'])
    if not cluster:
        sys.exit(1)

    logging.cluster = cluster['name']

    if only_when_required and not router['requiresupgrade']:
        logging.info(
            f"Router '{router['name']}' does not need to be upgraded. Will not reboot because --only-when-required was specified.")
        sys.exit(0)

    if cleanup:
        if not router['vpcid']:
            logging.error(f"Cleanup specified but no VPC ID found for router '{router['name']}'")
            sys.exit(1)

        logging.task = 'Restart VPC with clean up'

        vpc = co.get_vpc(id=router['vpcid'])
        if not vpc:
            sys.exit(1)

        if not vpc.restart():
            sys.exit(1)

        logging.info(f"Successfully restarted VPC '{vpc['name']}' with cleanup for router '{router['name']}'")
    else:
        logging.task = 'Reboot virtual router'

        if not router.reboot():
            sys.exit(1)

        logging.info(f"Successfully rebooted router '{router['name']}'", log_to_slack)


if __name__ == '__main__':
    main()

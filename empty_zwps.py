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

import re
import sys

import click
import click_log

from cosmicops import logging, CosmicOps


@click.command()
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.option('--virtual-machines', '-m', required=True, multiple=True,
              help='name of a virtualmachine, regex supported (e.g.: tla[td].*) (multiple are allowed)')
@click.argument('zwps_cluster')
@click.argument('destination_cluster')
def main(dry_run, zwps_cluster, destination_cluster, virtual_machines):
    """Empty ZWPS by migrating VMs and/or it's volumes to the destination cluster."""

    click_log.basic_config()

    profile = 'nl2'

    log_to_slack = True
    logging.task = 'Live Migrate VM Volumes'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    zwps_storage_pools = []
    for storage_pool in co.get_all_storage_pools():
        if zwps_cluster.upper() in storage_pool['name']:
            zwps_storage_pools.append(storage_pool)

    logging.info('ZWPS storage pools found:')
    for zwps_storage_pool in zwps_storage_pools:
        logging.info(f" - '{zwps_storage_pool['name']}'")

    destination_cluster = co.get_cluster(name=destination_cluster)
    if not destination_cluster:
        logging.error(f"Destination cluster not found:'{destination_cluster['name']}'!")
        sys.exit(1)

    volumes = []
    for zwps_storage_pool in zwps_storage_pools:
        vols = co.get_all_volumes(list_all=True, storageid=zwps_storage_pool['id'])
        if vols:
            volumes += vols

    vm_ids = []
    logging.info('Volumes found:')
    for volume in volumes:
        if re.search(virtual_machines, volume['vmname']):
            logging.info(f" - '{volume['name']}' on VM '{volume['vmname']}'")
            vm_ids.append(volume['virtualmachineid'])

    vms = []
    for vm_id in vm_ids:
        vm = co.get_vm(id=vm_id)
        vms.append(vm)

    logging.info('Virtualmachines found:')
    for vm in vms:
        logging.info(f" - '{vm['name']}'")


if __name__ == '__main__':
    main()

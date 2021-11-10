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
import datetime
import pytz
import re
import sys
import random

import click
import click_log

from cosmicops import logging, CosmicOps, CosmicSQL

from live_migrate_virtual_machine import live_migrate
from live_migrate_virtual_machine_volumes import live_migrate_volumes


@click.command()
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.option('--virtual-machines', '-m', required=True, multiple=True,
              help='name of a virtualmachine, regex supported (e.g.: tla[td].*) (multiple are allowed)')
@click.option('--force-end-hour', '-t',
              help='End hour after which we do not start new migrations. Example: 23 for 23:00 or 14 for 14:00')
@click.argument('zwps_cluster')
@click.argument('destination_cluster')
def main(dry_run, zwps_cluster, destination_cluster, virtual_machines, force_end_hour):
    """Empty ZWPS by migrating VMs and/or it's volumes to the destination cluster."""

    click_log.basic_config()

    if force_end_hour:
        try:
            force_end_hour = int(force_end_hour)
        except ValueError as e:
            logging.error(f"Specified time:'{force_end_hour}' is not a valid integer due to: '{e}'")
            sys.exit(1)
        if force_end_hour >= 24:
            logging.error(f"Specified time:'{force_end_hour}' should be < 24")
            sys.exit(1)

    profile = 'nl2'

    log_to_slack = True
    logging.task = 'Live Migrate VM Volumes'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    if not dry_run:
        cs = CosmicSQL(server=profile, dry_run=dry_run)
    else:
        cs = None

    zwps_storage_pools = []
    for storage_pool in co.get_all_storage_pools():
        if zwps_cluster.upper() in storage_pool['name']:
            zwps_storage_pools.append(storage_pool)

    logging.info('ZWPS storage pools found:')
    for zwps_storage_pool in zwps_storage_pools:
        logging.info(f" - '{zwps_storage_pool['name']}'")

    target_cluster = co.get_cluster(name=destination_cluster)
    if not target_cluster:
        logging.error(f"Destination cluster not found:'{target_cluster['name']}'!")
        sys.exit(1)

    try:
        destination_storage_pools = target_cluster.get_storage_pools(scope='CLUSTER')
    except IndexError:
        logging.error(f"No storage pools  found for cluster '{target_cluster['name']}'")
        sys.exit(1)
    logging.info('Destination storage pools found:')
    for target_storage_pool in destination_storage_pools:
        logging.info(f" - '{target_storage_pool['name']}'")

    target_storage_pool = random.choice(destination_storage_pools)

    volumes = []
    for zwps_storage_pool in zwps_storage_pools:
        vols = co.get_all_volumes(list_all=True, storageid=zwps_storage_pool['id'])
        if vols:
            volumes += vols

    vm_ids = []
    logging.info('Volumes found:')
    for volume in volumes:
        for virtual_machine in virtual_machines:
            if re.search(virtual_machine, volume['vmname']):
                logging.info(f" - '{volume['name']}' on VM '{volume['vmname']}'")
                if volume['virtualmachineid'] not in vm_ids:
                    vm_ids.append(volume['virtualmachineid'])

    vms = []
    for vm_id in vm_ids:
        vm = co.get_vm(id=vm_id)
        if vm['affinitygroup']:
            for affinitygroup in vm['affinitygroup']:
                if 'DedicatedGrp' in affinitygroup['name']:
                    logging.warning(f"Skipping VM '{vm['name']}' because of 'DedicatedGrp' affinity group")
                    continue
        vms.append(vm)

    logging.info('Virtualmachines found:')
    for vm in vms:
        logging.info(f" - '{vm['name']}'")

    logging.info(
        f"Starting live migration of volumes and/or virtualmachines from the ZWPS storage pools to storage pool '{target_cluster['name']}'")

    for vm in vms:
        """ Can we start a new migration? """
        if force_end_hour:
            now = datetime.datetime.now(pytz.timezone('CET'))
            if now.hour >= force_end_hour:
                logging.info(
                    f"Stopping migration batch. We are not starting new migrations after '{force_end_hour}':00",
                    log_to_slack=log_to_slack)
                sys.exit(0)

        source_host = co.get_host(id=vm['hostid'])
        source_cluster = co.get_cluster(zone='nl2', id=source_host['clusterid'])
        if source_cluster['name'] == target_cluster['name']:
            """ VM is already on the destination cluster, so we only need to migrate the volumes to this storage pool """
            logging.info(
                f"Starting live migration of volumes of VM '{vm['name']}' to storage pool '{target_storage_pool['name']}' ({target_storage_pool['id']})",
                log_to_slack=log_to_slack)
            live_migrate_volumes(target_storage_pool['name'], co, cs, dry_run, False, log_to_slack, 0, vm['name'], True)
        else:
            """ VM needs to be migrated live to the destination cluster, including volumes """
            live_migrate(co=co, cs=cs, cluster=target_cluster['name'], vm_name=vm['name'], destination_dc=None,
                         add_affinity_group=None, is_project_vm=None, zwps_to_cwps=True, log_to_slack=log_to_slack,
                         dry_run=dry_run)


if __name__ == '__main__':
    main()

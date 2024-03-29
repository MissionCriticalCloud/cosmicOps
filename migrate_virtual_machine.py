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
import time
from random import choice

import click
import click_log
import click_spinner

from cosmicops import CosmicOps, logging, CosmicSQL

DATACENTERS = ["SBP1", "EQXAMS2", "EVO"]


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--is-project-vm', is_flag=True, help='The specified VM is a project VM')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vm')
@click.argument('cluster')
@click.option('--destination-dc', '-d', metavar='<DC name>', help='Migrate to this datacenter')
@click.option('--destination-so', metavar='<Service Offering Name>', help='Switch to this service offering')
def main(profile, is_project_vm, dry_run, vm, cluster, destination_dc, destination_so):
    """Offline migrate VM to CLUSTER"""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Offline Migrate VM'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    cs = CosmicSQL(server=profile, dry_run=dry_run)

    target_cluster = co.get_cluster(name=cluster)
    if not target_cluster:
        sys.exit(1)

    vm = co.get_vm(name=vm, is_project_vm=is_project_vm)
    if not vm:
        sys.exit(1)

    if destination_dc and destination_dc not in DATACENTERS:
        logging.error(f"Unknown datacenter '{destination_dc}', should be one of {str(DATACENTERS)}")
        sys.exit(1)

    logging.instance_name = vm['instancename']
    logging.slack_value = vm['domain']
    logging.vm_name = vm['name']
    logging.zone_name = vm['zonename']

    target_storage_pool = None
    try:
        # Get CLUSTER scoped volume (no NVMe or ZONE-wide)
        while target_storage_pool is None or target_storage_pool['scope'] != 'CLUSTER':
            target_storage_pool = choice(target_cluster.get_storage_pools())
    except IndexError:
        logging.error(f"No storage pools found for cluster '{target_cluster['name']}")
        sys.exit(1)

    if vm['state'] == 'Running':
        need_to_stop = True
        auto_start_vm = True
    else:
        need_to_stop = False
        auto_start_vm = False

    if destination_dc:
        for datacenter in DATACENTERS:
            if datacenter == destination_dc:
                continue

            if datacenter in vm['serviceofferingname']:
                new_offering = vm['serviceofferingname'].replace(datacenter, destination_dc)
                logging.info(
                    f"Replacing '{vm['serviceofferingname']}' with '{new_offering}'")
                cs.update_service_offering_of_vm(vm['instancename'], new_offering)
                vm = co.get_vm(name=vm['instancename'], is_project_vm=is_project_vm)
                break

    if destination_so:
        logging.info(
            f"Replacing '{vm['serviceofferingname']}' with '{destination_so}'")
        cs.update_service_offering_of_vm(vm['instancename'], destination_so)
        vm = co.get_vm(name=vm['instancename'], is_project_vm=is_project_vm)

    vm_service_offering = co.get_service_offering(id=vm['serviceofferingid'])
    if vm_service_offering:
        storage_tags = vm_service_offering['tags'] if 'tags' in vm_service_offering else ''

        if not storage_tags:
            logging.warning('VM service offering has no storage tags')
        else:
            if storage_tags not in target_storage_pool['tags']:
                logging.error(
                    f"Can't migrate '{vm['name']}', storage tags on target cluster ({target_storage_pool['tags']}) to not contain the tags on the VM's service offering ({storage_tags})'")
                sys.exit(1)

    if need_to_stop:
        if not vm.stop():
            sys.exit(1)

    volumes = vm.get_volumes()

    for volume in volumes:
        if volume['storage'] == target_storage_pool['name']:
            logging.warning(
                f"Volume '{volume['name']}' ({volume['id']}) already on cluster '{target_cluster['name']}', skipping...")
            continue

        source_storage_pool = co.get_storage_pool(name=volume['storage'])
        if not source_storage_pool:
            sys.exit(1)

        if source_storage_pool['scope'] == 'ZONE':
            logging.warning(f"Scope of volume '{volume['name']}' ({volume['id']}) is ZONE, skipping...")
            continue

        if not volume.migrate(target_storage_pool):
            sys.exit(1)

        with click_spinner.spinner():
            while True:
                volume.refresh()

                if volume['state'] == 'Ready':
                    break

                logging.warning(
                    f"Volume '{volume['name']}' ({volume['id']}) is in '{volume['state']}' state instead of 'Ready', sleeping...")
                time.sleep(60)

    if auto_start_vm:
        destination_host = target_cluster.find_migration_host(vm)
        if not destination_host:
            sys.exit(1)

        if not vm.start(destination_host):
            sys.exit(1)
    else:
        logging.info(f"Not starting VM '{vm['name']}' as it was not running", log_to_slack)


if __name__ == '__main__':
    main()

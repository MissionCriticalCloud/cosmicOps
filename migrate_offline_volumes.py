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
from random import choice

import click
import click_log

from cosmicops import CosmicOps, logging, CosmicSQL


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--ignore-volumes', metavar='<list>', default=[], help='Comma separated list of volume IDs to skip')
@click.option('--skip-disk-offerings', metavar='<list>', help='Comma separated list of disk offerings to skip')
@click.option('--only-project', is_flag=True, help='Only migrate volumes belonging to project VMs')
@click.option('--zwps-to-cwps', is_flag=True, help='Migrate from ZWPS to CWPS')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('source_cluster')
@click.argument('destination_cluster')
def main(profile, dry_run, ignore_volumes, zwps_to_cwps, skip_disk_offerings, only_project, source_cluster, destination_cluster):
    """Migrate offline volumes from SOURCE_CLUSTER to DESTINATION_CLUSTER"""

    click_log.basic_config()

    if source_cluster == destination_cluster:
        logging.error('Destination cluster cannot be the same source cluster!')
        sys.exit(1)

    if dry_run:
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run)
    cs = CosmicSQL(server=profile, dry_run=dry_run)

    source_cluster = co.get_cluster(name=source_cluster)
    source_storage_pools = co.get_all_storage_pools(name=source_cluster)
    if not source_cluster and not source_storage_pools:
        logging.error(f"Source cluster not found:'{source_cluster}'!")
        sys.exit(1)

    destination_cluster = co.get_cluster(name=destination_cluster)
    if not destination_cluster:
        logging.error(f"Destination cluster not found:'{destination_cluster['name']}'!")
        sys.exit(1)

    if source_cluster:
        try:
            source_storage_pools = source_cluster.get_storage_pools(scope='CLUSTER')
        except IndexError:
            logging.error(f"No storage pools  found for cluster '{source_cluster['name']}'")
            sys.exit(1)

    logging.info('Source storage pools found:')
    for source_storage_pool in source_storage_pools:
        logging.info(f" - '{source_storage_pool['name']}'")

    try:
        destination_storage_pools = destination_cluster.get_storage_pools(scope='CLUSTER')
    except IndexError:
        logging.error(f"No storage pools  found for cluster '{destination_cluster['name']}'")
        sys.exit(1)
    logging.info('Destination storage pools found:')
    for destination_storage_pool in destination_storage_pools:
        logging.info(f" - '{destination_storage_pool['name']}'")

    if ignore_volumes:
        ignore_volumes = ignore_volumes.replace(' ', '').split(',')
        logging.info(f"Ignoring volumes: {str(ignore_volumes)}")

    if skip_disk_offerings:
        skip_disk_offerings = skip_disk_offerings.replace(' ', '').split(',')
        logging.info(f"Skipping disk offerings: {str(skip_disk_offerings)}")

    for source_storage_pool in source_storage_pools:
        destination_storage_pool = choice(destination_storage_pools)
        volumes = source_storage_pool.get_volumes(only_project)

        for volume in volumes:
            if volume['id'] in ignore_volumes:
                continue

            if skip_disk_offerings and volume.get('diskofferingname') in skip_disk_offerings:
                logging.warning(f"Volume '{volume['name']}' has offering '{volume['diskofferingname']}', skipping...")
                continue

            if 'storage' not in volume:
                logging.warning(f"No storage attribute found for volume '{volume['name']}' ({volume['id']}), skipping...")
                continue

            if volume['storage'] == destination_storage_pool['name']:
                logging.warning(
                    f"Volume '{volume['name']}' ({volume['id']}) already on cluster '{destination_cluster['name']}', skipping...")
                continue

            if volume['state'] != 'Ready':
                logging.warning(f"Volume '{volume['name']}' ({volume['id']}) is in state '{volume['state']}', skipping...")
                continue

            if 'vmstate' in volume and volume['vmstate'] != 'Stopped':
                logging.warning(
                    f"Volume '{volume['name']}' ({volume['id']}) is attached to {volume['vmstate']} VM '{volume['vmname']}', skipping...")
                continue

            if zwps_to_cwps:
                if not dry_run:
                    logging.info(
                        f"Converting ZWPS volume '{volume['name']}' to CWPS before starting the migration")
                    if not cs.update_zwps_to_cwps('MCC_v1.CWPS', volume_id=volume['id']):
                        logging.error(f"Failed to apply CWPS disk offering to volume '{volume['name']}'")
                        return False
                else:
                    logging.info(
                        f"Would have changed the diskoffering for volume '{volume['name']}' to CWPS before starting the migration")

            if source_cluster:
                logging.info(
                    f"Volume '{volume['name']}' will be migrated from cluster '{source_cluster['name']}' to '{destination_cluster['name']}'")
            else:
                logging.info(
                    f"Volume '{volume['name']}' will be migrated from storage pool '{source_storage_pool['name']}' to '{destination_cluster['name']}'")

            if not volume.migrate(destination_storage_pool):
                continue


if __name__ == '__main__':
    main()

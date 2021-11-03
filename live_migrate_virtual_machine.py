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
from datetime import datetime

from cosmicops import CosmicOps, logging, CosmicSQL

DATACENTERS = ["SBP1", "EQXAMS2", "EVO"]


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--zwps-to-cwps', is_flag=True, help='Migrate from ZWPS to CWPS')
@click.option('--add-affinity-group', metavar='<group name>', help='Add this affinity group after migration')
@click.option('--destination-dc', '-d', metavar='<DC name>', help='Migrate to this datacenter')
@click.option('--is-project-vm', is_flag=True, help='The specified VM is a project VM')
@click.option('--skip-within-cluster', is_flag=True, default=False, show_default=True,
              help='Enable/disable migration within cluster')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vm')
@click.argument('cluster')
def main(profile, zwps_to_cwps, add_affinity_group, destination_dc, is_project_vm,
         skip_within_cluster, dry_run, vm, cluster):
    """Live migrate VM to CLUSTER"""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Live Migrate VM'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    cs = CosmicSQL(server=profile, dry_run=dry_run)

    # Work around migration issue: first in the same pod to limit possible hiccup
    vm_instance = co.get_vm(name=vm, is_project_vm=is_project_vm)

    if not vm_instance:
        logging.error(f"Cannot migrate, VM '{vm}' not found!")
        sys.exit(1)

    if not vm_instance['state'] == 'Running':
        logging.error(f"Cannot migrate, VM has has state: '{vm_instance['state']}'")
        sys.exit(1)

    source_host = co.get_host(id=vm_instance['hostid'])
    source_cluster = co.get_cluster(id=source_host['clusterid'])
    if not skip_within_cluster:
        if not vm_instance.migrate_within_cluster(vm=vm_instance, source_cluster=source_cluster,
                                       source_host=source_host, instancename=vm_instance):
            logging.info(f"VM Migration failed at {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")
            sys.exit(1)

    if not live_migrate(co, cs, cluster, vm, destination_dc, add_affinity_group, is_project_vm, zwps_to_cwps,
                        log_to_slack, dry_run):
        logging.info(f"VM Migration failed at {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")
        sys.exit(1)
    logging.info(f"VM Migration completed at {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")


def live_migrate(co, cs, cluster, vm, destination_dc, add_affinity_group, is_project_vm, zwps_to_cwps, log_to_slack,
                 dry_run):
    if destination_dc and destination_dc not in DATACENTERS:
        logging.error(f"Unknown datacenter '{destination_dc}', should be one of {str(DATACENTERS)}")
        return False

    target_cluster = co.get_cluster(name=cluster)
    if not target_cluster:
        return False

    vm = co.get_vm(name=vm, is_project_vm=is_project_vm)
    if not vm:
        return False

    if not vm['state'] == 'Running':
        logging.error(f"Cannot migrate, VM has has state: '{vm['state']}'")
        return False

    for vm_snapshot in vm.get_snapshots():
        logging.error(f"Cannot migrate, VM has VM snapshots: '{vm_snapshot['name']}'")
        return False

    logging.instance_name = vm['instancename']
    logging.slack_value = vm['domain']
    logging.vm_name = vm['name']
    logging.zone_name = vm['zonename']

    source_host = co.get_host(id=vm['hostid'])
    if not source_host:
        return False

    source_cluster = co.get_cluster(id=source_host['clusterid'])
    if not source_cluster:
        return False

    logging.cluster = source_cluster['name']
    if source_cluster['id'] == target_cluster['id']:
        logging.error(f"VM '{vm['name']}' is already running on cluster '{target_cluster['name']}'")
        return False

    if not dry_run:
        disk_info = source_host.get_disks(vm)
        for path, disk_info in disk_info.items():
            _, path, _, _, size = cs.get_volume_size(path)

            if int(size) != int(disk_info['size']):
                logging.warning(
                    f"Size for '{disk_info['path']}' in DB ({size}) is less than libvirt reports ({disk_info['size']}), updating DB")
                cs.update_volume_size(vm['instancename'], path, disk_info['size'])

    if zwps_to_cwps:
        if not dry_run:
            logging.info(f"Converting any ZWPS volume of VM '{vm['name']}' to CWPS before starting the migration",
                         log_to_slack=log_to_slack)
            if not cs.update_zwps_to_cwps(vm['instancename'], 'MCC_v1.CWPS'):
                logging.error(f"Failed to apply CWPS disk offering to VM '{vm['name']}'", log_to_slack=log_to_slack)
                return False
        else:
            logging.info('Would have changed the diskoffering from ZWPS to CWPS of all ZWPS volumes')

    if destination_dc:
        for datacenter in DATACENTERS:
            if datacenter == destination_dc:
                continue

            if datacenter in vm['serviceofferingname']:
                logging.info(
                    f"Replacing '{datacenter}' with '{destination_dc}' in offering '{vm['serviceofferingname']}'")
                cs.update_service_offering_of_vm(vm['instancename'],
                                                 vm['serviceofferingname'].replace(datacenter, destination_dc))
                break

    zwps_found = False
    zwps_name = None
    root_disk = None
    cwps_found = False
    hwps_found = False
    data_disks_to_zwps = []
    zwps_disks_to_cwps = []
    for volume in vm.get_volumes():
        for snapshot in volume.get_snapshots():
            logging.error(f"Cannot migrate, volume '{volume['name']}' has snapshot: '{snapshot['name']}'")
            return False

        if volume['type'] == 'DATADISK':
            if volume['state'] != 'Ready':
                logging.error(f"Volume '{volume['name']}' has non-READY state '{volume['state']}'. halting")
                return False

            source_storage_pool = co.get_storage_pool(name=volume['storage'])

            if source_storage_pool['scope'] == 'CLUSTER':
                cwps_found = True
                data_disks_to_zwps.append(volume)
            elif source_storage_pool['scope'] == 'ZONE':
                zwps_found = True
                zwps_name = volume['storage']
                if zwps_to_cwps:
                    zwps_disks_to_cwps.append(volume)
            elif source_storage_pool['scope'] == 'HOST':
                hwps_found = True
        elif volume['type'] == 'ROOT':
            root_disk = volume

    if hwps_found:
        logging.error(f"VM '{vm['name']} has HWPS data disks attached. This is currently not handled by this script.",
                      log_to_slack=log_to_slack)
        return False

    if cwps_found and zwps_found:
        logging.info(
            f"VM '{vm['name']}' has both ZWPS and CWPS data disks attached. We are going to temporarily migrate all CWPS volumes to ZWPS.",
            log_to_slack=log_to_slack)
        for volume in data_disks_to_zwps:
            if not temp_migrate_volume(co=co, dry_run=dry_run, log_to_slack=log_to_slack, volume=volume,
                                       vm=vm, target_pool_name=zwps_name):
                logging.error(f"Volume '{volume['name']}'failed to migrate")
                return False

    if zwps_found:
        logging.info(f"ZWPS data disk attached to VM '{vm['name']}")
        logging.info(
            f"For migration to succeed we need to migrate root disk '{root_disk['name']}' to ZWPS pool '{zwps_name}' first")

        if root_disk['storage'] == zwps_name:
            logging.warning(f"Volume '{root_disk['name']}' already on desired storage pool")
        else:
            if not temp_migrate_volume(co=co, dry_run=dry_run, log_to_slack=log_to_slack, volume=root_disk,
                                       vm=vm, target_pool_name=zwps_name):
                logging.error(f"Volume '{root_disk['name']}'failed to migrate")
                return False

    logging.info(f"ROOT disk is at storage pool: '{root_disk['storage']}'")

    destination_host = target_cluster.find_migration_host(vm)
    if not destination_host:
        return False

    if dry_run:
        if add_affinity_group:
            logging.info(
                f"Would have added affinity group '{add_affinity_group}' to VM '{vm['name']}'")
        logging.info(
            f"Would live migrate VM '{vm['name']}' to '{destination_host['name']}'")
        return True

    root_storage_pool = co.get_storage_pool(name=root_disk['storage'])
    if not root_storage_pool:
        logging.error(f"Unable to fetch storage pool details foor ROOT disk '{root_disk['name']}'",
                      log_to_slack=log_to_slack)
        return False

    migrate_with_volume = False if root_storage_pool['scope'] == 'ZONE' else True

    if migrate_with_volume:
        for volume in vm.get_volumes():
            for target_pool in co.get_all_storage_pools(clusterid=target_cluster['id']):
                if not clean_old_disk_file(co=co, host=destination_host, dry_run=dry_run, volume=volume,
                                           target_pool_name=target_pool['name']):
                    logging.error(f"Cleaning volume '{root_disk['name']}' failed")
                    return False

    if not vm.migrate(destination_host, with_volume=migrate_with_volume,
                      source_host=source_host, instancename=vm['instancename']):
        return False

    with click_spinner.spinner():
        while True:
            vm.refresh()

            if vm['state'] == 'Running':
                break

            logging.warning(f"VM '{vm['name']} is in '{vm['state']}' state instead of 'Running', sleeping...")
            time.sleep(60)

    if source_host['name'] == vm['hostname']:
        logging.error(
            f"VM '{vm['name']}' failed to migrate to '{destination_host['name']}' on cluster '{target_cluster['name']}'")
        return False
    else:
        if add_affinity_group:
            if not cs.add_vm_to_affinity_group(vm['instancename'], add_affinity_group):
                logging.error(
                    f"Failed to add affinity group '{add_affinity_group}' to VM '{vm['name']}'")
            else:
                logging.info(
                    f"Successfully added affinity group '{add_affinity_group}' to VM '{vm['name']}'")

        logging.info(
            f"VM '{vm['name']}' successfully migrated to '{destination_host['name']}' on cluster '{target_cluster['name']}'")

    if not migrate_with_volume:
        vm.refresh()
        target_pool = choice(target_cluster.get_storage_pools(scope='CLUSTER'))
        if not temp_migrate_volume(co=co, dry_run=dry_run, log_to_slack=log_to_slack, volume=root_disk,
                                   vm=vm, target_pool_name=target_pool['name']):
            logging.error(f"Volume '{root_disk['name']}'failed to migrate")
            return False
        if cwps_found and zwps_found:
            for volume in data_disks_to_zwps:
                target_pool = choice(target_cluster.get_storage_pools(scope='CLUSTER'))
                if not temp_migrate_volume(co=co, dry_run=dry_run, log_to_slack=log_to_slack, volume=volume,
                                           vm=vm, target_pool_name=target_pool['name']):
                    logging.error(f"Volume '{volume['name']}'failed to migrate")
                    return False
        if zwps_to_cwps:
            for volume in zwps_disks_to_cwps:
                target_pool = choice(target_cluster.get_storage_pools(scope='CLUSTER'))
                if not temp_migrate_volume(co=co, dry_run=dry_run, log_to_slack=log_to_slack, volume=volume,
                                           vm=vm, target_pool_name=target_pool['name']):
                    logging.error(f"Volume '{volume['name']}'failed to migrate")
                    return False

    return True


# Function to temporarily migrate CWPS volumes to and from ZWPS to perform a migration of VMs with ZWPS volumes
def temp_migrate_volume(co, dry_run, log_to_slack, volume, vm, target_pool_name):
    vm.refresh()
    source_host = co.get_host(id=vm['hostid'])
    if not source_host:
        logging.error(f"Source host not found for '{vm['name']}' using '{vm['hostid']}'!")
        return False
    target_storage_pool = co.get_storage_pool(name=target_pool_name)
    if not target_storage_pool:
        return False
    if not co.clean_old_disk_file(host=source_host, dry_run=dry_run, volume=volume,
                                  target_pool_name=target_pool_name):
        logging.error(f"Cleaning volume '{volume['name']}' failed on zwps")
        return False
    if dry_run:
        logging.info(
            f"Would migrate volume '{volume['name']}' of VM '{vm['name']}' to pool '{target_pool_name}'")
    else:
        logging.info(
            f"Migrating volume '{volume['name']}' of VM '{vm['name']}' to pool '{target_pool_name}'",
            log_to_slack=log_to_slack)

        if not volume.migrate(target_storage_pool, live_migrate=True, source_host=source_host,
                              vm=vm, vol=volume['path']):
            logging.error(f"Migration failed for volume '{volume['name']}' of VM '{vm['name']}'",
                          log_to_slack=log_to_slack)
            return False
        logging.info(
            f"Migration completed of volume '{volume['name']}' of VM '{vm['name']}' to pool '{target_pool_name}'",
            log_to_slack=log_to_slack)
    return True


if __name__ == '__main__':
    main()

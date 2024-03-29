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
from operator import itemgetter
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
@click.option('--migrate-offline-with-rsync', is_flag=True, help='Migrate offline using rsync. Use for large disks.')
@click.option('--rsync-target-host', help='Name of the rsync target server')
@click.option('--add-affinity-group', metavar='<group name>', help='Add this affinity group after migration')
@click.option('--destination-dc', '-d', metavar='<DC name>', help='Migrate to this datacenter')
@click.option('--is-project-vm', is_flag=True, help='The specified VM is a project VM')
@click.option('--avoid-storage-pool', default=None, help='Do not attempt migrate to this storage pool')
@click.option('--skip-backingfile-merge', is_flag=True, help='Do not attempt merge backing file')
@click.option('--skip-within-cluster', is_flag=True, default=False, show_default=True,
              help='Enable/disable migration within cluster')
@click.option('--only-within-cluster', is_flag=True, default=False, show_default=True,
              help='Only do migration within cluster')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vm-name')
@click.argument('cluster', required=False)
def main(profile, zwps_to_cwps, migrate_offline_with_rsync, rsync_target_host, add_affinity_group, destination_dc, is_project_vm,
         avoid_storage_pool, skip_backingfile_merge, skip_within_cluster, only_within_cluster, dry_run, vm_name, cluster):
    """Live migrate VM"""
    """Unless --migrate-offline-with-rsync is passed, then we migrate offline"""
    # TODO break this down into funtions no more than 30 lines  # noqa
    # TODO change the default behaviour to "migrate within the current cluster" and add a specific option to "migrate to another cluster" e.g. --to-cluster  # noqa

    # 2022-01-01, after an upgrade of an unknow component of KVM/CentOS, the migration to another cluster caused a network hiccup,
    # the migration within a cluster is added to mitigate a network hiccup during a migration to another cluster

    # Live migrate requires running VM. Unless migrate_offline_with_rsync==True, then we stop the VM as this is offline


    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Live Migrate VM'
    if migrate_offline_with_rsync:
        logging.task = 'Offline Migrate VM using rsync'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    cs = CosmicSQL(server=profile, dry_run=dry_run)

    vm = co.get_vm(name=vm_name, is_project_vm=is_project_vm)

    if not vm:
        logging.error(f"Cannot migrate, VM '{vm_name}' not found!")
        sys.exit(1)

    if skip_within_cluster and only_within_cluster:
        logging.error(f"Cannot use 'skip_within_cluster' together with 'only_within_cluster'!")
        sys.exit(1)

    if not only_within_cluster and not cluster:
        logging.error(f"We need a cluster name if you're not only migrating within the cluster!")
        sys.exit(1)

    if not migrate_offline_with_rsync:
        if not vm['state'] == 'Running':
            logging.error(f"Cannot migrate, VM has has state: '{vm['state']}'")
            sys.exit(1)

        source_host = co.get_host(id=vm['hostid'])
        source_cluster = co.get_cluster(id=source_host['clusterid'])
        if not skip_within_cluster:
            if not vm.migrate_within_cluster(vm=vm, source_cluster=source_cluster,
                                                      source_host=source_host):
                logging.info(f"VM Migration failed at {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")
                sys.exit(1)

        if not only_within_cluster:
            if not live_migrate(co, cs, cluster, vm_name, destination_dc, add_affinity_group, is_project_vm, zwps_to_cwps,
                                log_to_slack, dry_run):
                logging.info(f"VM Migration failed at {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")
                sys.exit(1)
        logging.info(f"VM Migration completed at {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")

    if migrate_offline_with_rsync:
        if rsync_target_host is None:
            example_target = "%s-hv01" % cluster.split('-')[0]
            logging.error(f"Invalid options! Please specify --rsync-target-host."
                          f" Example: --rsync-target-host {example_target}")
            sys.exit(1)

        if vm['state'] == 'Running':
            need_to_stop = True
            auto_start_vm = True
        elif vm['state'] == 'Stopped':
            need_to_stop = False
            auto_start_vm = False
        else:
            logging.error(f"Cannot migrate, VM '{vm_name}' should be in Running or Stopped state!", log_to_slack=True)
            sys.exit(1)

        logging.info(f"VM Migration using rsync method starting for vm {vm['name']}")

        if not vm['state'] == 'Running' and not skip_backingfile_merge:
            logging.error(f"Cannot migrate, VM has has state: '{vm['state']}'. In order to merge backing"
                          f" files, we need to have a Running VM. We will stop the VM later! You can also skip"
                          f" backing file merging by providing flag --skip-backingfile-merge")
            sys.exit(1)

        # Make sure backing file is merged into disk. VM needs to be Running for this to work
        if skip_backingfile_merge:
            logging.info(
                f"Skipping backing file merging due to --skip-backingfile-merge")
        else:
            running_host = co.get_host(name=vm['hostname'])

            if not dry_run:
                if not running_host.merge_backing_files(vm):
                    return False
            else:
                logging.info(
                    f"Would have merged all backing files if any exist on {running_host['name']}")

        if need_to_stop:
            if not vm.stop():
                logging.error(f"Stopping failed for VM '{vm['state']}'", log_to_slack=True)
                sys.exit(1)

        # Manually set migrating state to prevent unwanted VM starts
        if not cs.set_vm_state(instance_name=vm['instancename'], status_name='Migrating'):
            logging.error(f"Cannot set status to Migrating for VM '{vm_name}'!", log_to_slack=True)
            sys.exit(1)

        # Here our VM is stopped

        target_storage_pool = None
        target_cluster = co.get_cluster(name=cluster)

        target_hosts = target_cluster.get_all_hosts()
        target_hosts.sort(key=itemgetter('name'))

        target_host = target_hosts[0]

        for host in target_hosts:
            if rsync_target_host in host['name']:
                target_host = co.get_host(name=rsync_target_host)
                break

        if not target_host:
            logging.error(f"Cannot find host by name: {rsync_target_host}")
            sys.exit(1)

        logging.debug(f"Found target hosts: {target_host}")

        volumes = vm.get_volumes()
        volume_id = 0
        volume_counter = 0
        volume_destination_map = {}

        for volume in volumes:
            volume_counter += 1

            storage_pools = sorted(target_cluster.get_storage_pools(), key=lambda h: h['disksizeused'])
            for storage_pool in storage_pools:
                if storage_pool['scope'] == 'HOST':
                    continue
                if storage_pool['state'] == 'Maintenance':
                    continue
                if storage_pool['name'] == avoid_storage_pool:
                    continue
                free_space_bytes = int(storage_pool['disksizetotal']) - int(storage_pool['disksizeused'])
                needed_bytes = volume['size'] * 1.5
                if needed_bytes >= free_space_bytes:
                    continue
                target_storage_pool = storage_pool
                break

            if target_storage_pool is None:
                logging.warning(f"Unable to find storage pool for volume '{volume['name']}'"
                                f" ({round(volume['size']/1024/1024/1024,1)}GB)")
                sys.exit(1)

            if volume['storage'] == target_storage_pool['name']:
                logging.warning(
                    f"Volume '{volume['name']}' ({volume['id']}) already on cluster '{target_cluster['name']}/{target_storage_pool['name']}', skipping..")
                volumes.pop(volume_id)
                continue

            source_storage_pool = co.get_storage_pool(name=volume['storage'])
            if not source_storage_pool:
                sys.exit(1)

            if source_storage_pool['scope'] == 'ZONE':
                logging.warning(f"Scope of volume '{volume['name']}' ({volume['id']}) is ZONE, skipping..")
                continue

            # Current hostname and cluster
            source_cluster = co.get_cluster(id=source_storage_pool['clusterid'])
            source_hosts = source_cluster.get_all_hosts()
            source_hosts.sort(key=itemgetter('name'))
            source_host = source_hosts[0]

            volume_destination_map[volume['id']] = {
                'target_storage_pool': target_storage_pool,
                'source_storage_pool': source_storage_pool,
                'source_host_id': source_host['id'],
                'target_host_id': target_host['id']
            }

            # make sure staging folder exists
            logging.info(f"Making sure staging folder /mnt/{target_storage_pool['id']}/staging/ exists on '{target_storage_pool['name']}'..")
            target_host.execute(f"mkdir -p /mnt/{target_storage_pool['id']}/staging/", sudo=True, hide_stdout=False, pty=True)

            logging.info(
                f"Rsyncing volume {volume['name']} ({round(volume['size']/1024/1024/1024, 1)}GB) to storage pool {target_storage_pool['name']}"
                f" ({ volume_counter }/{ len(volumes) })", log_to_slack=not dry_run)

            # rsync volume naar staging
            source_host.execute(f"rsync -avP --sparse --whole-file --block-size=4096 /mnt/{source_storage_pool['id']}/{volume['path']} rsync://{target_host['ipaddress']}/{target_storage_pool['id']}",
                                sudo=True, hide_stdout=False, pty=True)

            volume_id += 1

        # Here all the disks are rsync'ed
        # We could implement something that can do this again to copy changed blocks

        logging.info(
            f"Finished migrating { volume_counter } volumes", log_to_slack=not dry_run)

        # Finally, move volumes in place and update the db
        for volume in volumes:
            # Check if VM is still stopped
            vm = co.get_vm(name=vm_name, is_project_vm=is_project_vm)
            if not dry_run and vm['state'] != 'Migrating':
                logging.error(f"Cannot migrate, VM has state: '{vm['state']}'")
                sys.exit(1)

            # skip if we did not rsync the volume
            if volume['id'] not in volume_destination_map:
                continue
            target_storage_pool = volume_destination_map[volume['id']]['target_storage_pool']
            source_storage_pool = volume_destination_map[volume['id']]['source_storage_pool']
            source_host_id = volume_destination_map[volume['id']]['source_host_id']
            source_host = co.get_host(id=source_host_id)
            target_host_id = volume_destination_map[volume['id']]['target_host_id']
            target_host = co.get_host(id=target_host_id)

            # move volume from staging to live
            target_host.execute(f"mv /mnt/{target_storage_pool['id']}/staging/{volume['path']} /mnt/{target_storage_pool['id']}/{volume['path']}",
                                sudo=True, hide_stdout=False, pty=True)
            # Update db
            cs = CosmicSQL(server=profile, dry_run=dry_run)
            volume_db_id = cs.get_volume_db_id(path=volume['path'])
            current_pool_db_id = cs.get_storage_pool_id_from_name(storage_pool_name=volume['storage'])
            target_pool_db_id = cs.get_storage_pool_id_from_name(storage_pool_name=target_storage_pool['name'])
            cs.update_storage_pool_id(volume_db_id=volume_db_id, current_pool_db_id=current_pool_db_id, new_pool_db_id=target_pool_db_id)

            # Add safety check via API: is volume on the expected storage pool now?
            if not dry_run:
                update_volume = co.get_volume(id=volume['id'])
                if update_volume['storageid'] != target_storage_pool['id']:
                    logging.error(f"Update volume '{volume['name']}' failed, investigate!")
                    sys.exit(1)
                logging.info(f"Updating volume '{volume['name']}' successfully set to pool '{target_storage_pool['name']}'!")

            # Rename old volumes to prevent unwanted start on old location
            timestamp = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
            source_host.execute(f"mv /mnt/{source_storage_pool['id']}/{volume['path']} /mnt/{source_storage_pool['id']}/{volume['path']}.rsync-migrated-{timestamp}",
                                sudo=True, hide_stdout=False, pty=True)

        # Reset custom state back to Stopped
        if not cs.set_vm_state(instance_name=vm['instancename'], status_name='Stopped'):
            logging.error(f"Cannot set status to Stopped for VM '{vm_name}'!", log_to_slack=True)
            sys.exit(1)

        # Start vm again if needed
        if auto_start_vm:
            vm = co.get_vm(name=vm_name, is_project_vm=is_project_vm)
            # Make sure status is stopped
            if not dry_run:
                retry_count = 0
                while vm['state'] != 'Stopped':
                    logging.info(f"VM '{vm_name}' has state '{vm['state']}': waiting for status 'Stopped'")
                    vm.refresh()
                    time.sleep(15)
                    retry_count += 1
                    if retry_count > 6:
                        break

            destination_host = target_cluster.find_migration_host(vm)
            if not destination_host:
                logging.error(f"Starting failed for VM '{vm['name']}': no destination host found", log_to_slack=True)
                sys.exit(1)
            # Start on a specific host to prevent unwanted migrations back to source
            if not vm.start(destination_host):
                logging.error(f"Starting failed for VM '{vm['name']}'", log_to_slack=True)
                sys.exit(1)
        logging.info(f"VM Migration completed at {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")


def live_migrate(co, cs, cluster, vm_name, destination_dc, add_affinity_group, is_project_vm, zwps_to_cwps,
                 log_to_slack, dry_run):
    if destination_dc and destination_dc not in DATACENTERS:
        logging.error(f"Unknown datacenter '{destination_dc}', should be one of {str(DATACENTERS)}")
        return False

    target_cluster = co.get_cluster(name=cluster)
    if not target_cluster:
        logging.error(f"Cannot migrate, cluster '{cluster}' not found!")
        return False

    vm = co.get_vm(name=vm_name, is_project_vm=is_project_vm)
    if not vm:
        logging.error(f"Cannot migrate, VM '{vm_name}' not found!")
        return False

    if not vm['state'] == 'Running':
        logging.error(f"Cannot migrate, VM has state: '{vm['state']}'")
        return False

    for vm_snapshot in vm.get_snapshots():
        logging.error(f"Cannot migrate, VM has VM snapshots: '{vm_snapshot['name']}'")
        return False

    if 'maintenancepolicy' in vm and vm['maintenancepolicy'] == 'ShutdownAndStart':
        logging.error(f"Cannot migrate, VM has maintenance policy: '{vm['maintenancepolicy']}'")
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
        disk_info = source_host.get_disks(vm['instancename'])
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
            if not cs.update_zwps_to_cwps('MCC_v1.CWPS', instance_name=vm['instancename']):
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
        logging.info(
            f"No hypervisor found to migrate to for VM '{vm['name']}'. Dedication?")
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
                if not co.clean_old_disk_file(host=destination_host, dry_run=dry_run, volume=volume,
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

        if not volume.migrate(target_storage_pool, live_migrate=True, source_host=source_host, vm_instancename=vm['instancename']):
            logging.error(f"Migration failed for volume '{volume['name']}' of VM '{vm['name']}'",
                          log_to_slack=log_to_slack)
            return False
        logging.info(
            f"Migration completed of volume '{volume['name']}' of VM '{vm['name']}' to pool '{target_pool_name}'",
            log_to_slack=log_to_slack)
    return True


if __name__ == '__main__':
    main()

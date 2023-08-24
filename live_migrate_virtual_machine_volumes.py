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

import click
import click_log
import click_spinner

from cosmicops import CosmicOps, logging, CosmicSQL


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--max-iops', '-m', metavar='<# IOPS>', default=1000, show_default=True,
              help='Limit amount of IOPS used during migration, use 0 to disable')
@click.option('--zwps-to-cwps', is_flag=True, help='Migrate from ZWPS to CWPS')
@click.option('--is-router', is_flag=True, help='The specified VM is a router')
@click.option('--is-project-vm', is_flag=True, help='The specified VM is a project VM')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vm')
@click.argument('storage_pool')
def main(profile, max_iops, zwps_to_cwps, is_router, is_project_vm, dry_run, vm, storage_pool):
    """Live migrate VM volumes to STORAGE_POOL"""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Live Migrate VM Volumes'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    cs = CosmicSQL(server=profile, dry_run=dry_run)

    if not live_migrate_volumes(storage_pool, co, cs, dry_run, is_router, is_project_vm, log_to_slack, max_iops, vm,
                                zwps_to_cwps):
        sys.exit(1)


def live_migrate_volumes(target_storage_pool_name, co, cs, dry_run, is_router, is_project_vm, log_to_slack, max_iops, vm_name, zwps_to_cwps):
    target_storage_pool = co.get_storage_pool(name=target_storage_pool_name)
    if not target_storage_pool:
        return False

    # disable setting max IOPS, if max_iops != 0
    set_max_iops = max_iops != 0

    if is_router:
        vm = co.get_router(name=vm_name,is_project_router=is_project_vm)
    else:
        vm = co.get_vm(name=vm_name, is_project_vm=is_project_vm)
    if not vm:
        logging.error(f"Failed to find VM with name: '{vm_name}'", log_to_slack=False)
        return False

    if is_router:
        logging.instance_name = vm['name']
        vm_instance = vm['name']
    else:
        logging.instance_name = vm['instancename']
        vm_instance = vm['instancename']
    logging.slack_value = vm['domain']
    logging.vm_name = vm['name']
    logging.zone_name = vm['zonename']

    if vm['state'] != 'Running':
        logging.error(f"Failed, VM with name: '{vm_name}' is not in state 'Running'!", log_to_slack=False)
        return False


    logging.info(
        f"Starting live migration of volumes of VM '{vm['name']}' to storage pool '{target_storage_pool['name']}' ({target_storage_pool['id']})",
        log_to_slack=log_to_slack)

    host = co.get_host(id=vm['hostid'])
    if not host:
        logging.error(f"Failed to get host with host_id: '{vm['hostid']}'", log_to_slack=False)
        return False

    cluster = co.get_cluster(id=host['clusterid'])
    if not cluster:
        logging.error(f"Failed to get cluster with cluster_id: '{host['clusterid']}'", log_to_slack=False)
        return False

    logging.cluster = cluster['name']

    if zwps_to_cwps:
        if not dry_run:
            logging.info(f"Converting any ZWPS volume of VM '{vm['name']}' to CWPS before starting the migration",
                         log_to_slack=log_to_slack)
            if not cs.update_zwps_to_cwps('MCC_v1.CWPS', instance_name=vm['instancename']):
                logging.error(f"Failed to apply CWPS disk offering to VM '{vm['name']}'", log_to_slack=log_to_slack)
                return False
        else:
            logging.info('Would have changed the diskoffering from ZWPS to CWPS of all ZWPS volumes')

    if not dry_run:
        disk_info = host.get_disks(vm_instance)
        for path, disk_info in disk_info.items():
            _, path, _, _, size = cs.get_volume_size(path)

            if int(size) != int(disk_info['size']):
                logging.warning(
                    f"Size for '{disk_info['path']}' in DB ({size}) is less than libvirt reports ({disk_info['size']}), updating DB")
                cs.update_volume_size(vm['instancename'], path, disk_info['size'])

    if set_max_iops:
        if not dry_run:
            if not host.set_iops_limit(vm_instance, max_iops):
                return False
        else:
            logging.info(
                f"Would have set an IOPS limit to '{max_iops}'")
    else:
        logging.info(
            f'Not setting an IOPS limit as it is disabled')

    if not dry_run:
        if not host.merge_backing_files(vm_instance):
            if set_max_iops:
                host.set_iops_limit(vm_instance, 0)
            return False
    else:
        logging.info(
            f'Would have merged all backing files if any exist')

    for volume in vm.get_volumes():
        if volume['storageid'] == target_storage_pool['id']:
            logging.warning(f"Skipping volume '{volume['name']}' as it's already on the specified storage pool",
                            log_to_slack=log_to_slack)
            continue

        source_storage_pool = co.get_storage_pool(id=volume['storageid'])
        if not source_storage_pool:
            continue

        if source_storage_pool['scope'] == 'HOST' or (source_storage_pool['scope'] == 'ZONE' and not zwps_to_cwps):
            logging.warning(f"Skipping volume '{volume['name']}' as it's scope is '{source_storage_pool['scope']}'",
                            log_to_slack=log_to_slack)
            continue

        if not co.clean_old_disk_file(host=host, dry_run=dry_run, volume=volume,
                                      target_pool_name=target_storage_pool['name']):
            logging.error(f"Cleaning volume '{volume['name']}' failed on zwps")
            return False
        if dry_run:
            logging.info(
                f"Would migrate volume '{volume['name']}' to storage pool '{target_storage_pool['name']}' ({target_storage_pool['id']})")
            continue

        logging.info(
            f"Starting migration of volume '{volume['name']}' from storage pool '{source_storage_pool['name']}' to storage pool '{target_storage_pool['name']}' ({target_storage_pool['id']})",
            log_to_slack=log_to_slack)

        # get the source host to read the blkjobinfo
        source_host = co.get_host(id=vm['hostid'])

        if not volume.migrate(target_storage_pool, live_migrate=True, source_host=source_host, vm_instance=vm_instance):
            continue

        with click_spinner.spinner():
            while True:
                volume.refresh()

                if volume['state'] == 'Ready':
                    break

                logging.warning(
                    f"Volume '{volume['name']}' is in '{volume['state']}' state instead of 'Ready', sleeping...")
                time.sleep(60)

        logging.info(
            f"Finished migration of volume '{volume['name']}' from storage pool '{source_storage_pool['name']}' to storage pool '{target_storage_pool['name']}' ({target_storage_pool['id']})",
            log_to_slack=log_to_slack)

    logging.info(
        f"Finished live migration of volumes of VM '{vm['name']}' to storage pool '{target_storage_pool['name']}' ({target_storage_pool['id']})",
        log_to_slack=log_to_slack)

    if set_max_iops:
        if not dry_run:
            host.set_iops_limit(vm_instance, 0)
        else:
            logging.info(
                f"Would have disable an IOPS limit")

    return True


if __name__ == '__main__':
    main()

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
              help='Limit amount of IOPS used during migration')
@click.option('--zwps-to-cwps', is_flag=True, help='Migrate from ZWPS to CWPS')
@click.option('--is-project-vm', is_flag=True, help='The specified VM is a project VM')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vm')
@click.argument('storage_pool')
def main(profile, max_iops, zwps_to_cwps, is_project_vm, dry_run, vm, storage_pool):
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

    if not live_migrate_volumes(storage_pool, co, cs, dry_run, is_project_vm, log_to_slack, max_iops, vm,
                                zwps_to_cwps):
        sys.exit(1)


def live_migrate_volumes(storage_pool, co, cs, dry_run, is_project_vm, log_to_slack, max_iops, vm, zwps_to_cwps):
    storage_pool = co.get_storage_pool(name=storage_pool)
    if not storage_pool:
        return False

    vm = co.get_vm(name=vm, is_project_vm=is_project_vm)
    if not vm:
        return False

    logging.instance_name = vm['instancename']
    logging.slack_value = vm['domain']
    logging.vm_name = vm['name']
    logging.zone_name = vm['zonename']

    host = co.get_host(id=vm['hostid'])
    if not host:
        return False

    cluster = co.get_cluster(id=host['clusterid'])
    if not cluster:
        return False

    logging.cluster = cluster['name']

    if zwps_to_cwps:
        logging.info(f"Converting any ZWPS volume of VM '{vm['name']}' to CWPS before starting the migration",
                     to_slack=log_to_slack)
        if not cs.update_zwps_to_cwps(vm['instancename'], 'MCC_v1.CWPS'):
            logging.error(f"Failed to apply CWPS disk offering to VM '{vm['name']}'", to_slack=log_to_slack)
            return False

    if not dry_run:
        disk_info = host.get_disks(vm)
        for path, disk_info in disk_info.items():
            _, path, _, _, size = cs.get_volume_size(path)

            if int(size) != int(disk_info['size']):
                logging.warning(
                    f"Size for '{disk_info['path']}' in DB ({size}) is less than libvirt reports ({disk_info['size']}), updating DB")
                cs.update_volume_size(vm['instancename'], path, disk_info['size'])

    if not host.set_iops_limit(vm, max_iops):
        return False

    if not host.merge_backing_files(vm):
        host.set_iops_limit(vm, 0)
        return False

    for volume in vm.get_volumes():
        if volume['storage'] == storage_pool['id']:
            logging.warning(f"Skipping volume '{volume['name']}' as it's already on the specified storage pool",
                            to_slack=log_to_slack)
            continue

        current_storage_pool = co.get_storage_pool(id=volume['storage'])
        if not current_storage_pool:
            continue

        if current_storage_pool['scope'] in ('Host', 'ZONE'):
            logging.warning(f"Skipping volume '{volume['name']}' as it's scope is '{current_storage_pool['scope']}'",
                            to_slack=log_to_slack)
            continue

        if dry_run:
            logging.info(
                f"Would migrate volume '{volume['name']}' to storage pool '{storage_pool['name']}' ({storage_pool['id']})")
            continue

        if not volume.migrate(storage_pool, live_migrate=True):
            continue

        with click_spinner.spinner():
            while True:
                volume.refresh()

                if volume['state'] == 'Ready':
                    break

                logging.warning(
                    f"Volume '{volume['name']}' is in '{volume['state']}' state instead of 'Ready', sleeping...")
                time.sleep(60)

    host.set_iops_limit(vm, 0)

    return True


if __name__ == '__main__':
    main()

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

DATACENTERS = ["SBP1", "EQXAMS2", "EVO"]


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--zwps-to-cwps', is_flag=True, help='Migrate from ZWPS to CWPS')
@click.option('--add-affinity-group', metavar='<group name>', help='Add this affinity group after migration')
@click.option('--destination-dc', '-d', metavar='<DC name>', help='Migrate to this datacenter')
@click.option('--is-project-vm', is_flag=True, help='The specified VM is a project VM')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vm')
@click.argument('cluster')
def main(profile, zwps_to_cwps, add_affinity_group, destination_dc, is_project_vm, dry_run, vm, cluster):
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

    if not live_migrate(co, cs, cluster, vm, destination_dc, add_affinity_group, is_project_vm, zwps_to_cwps,
                        log_to_slack, dry_run):
        sys.exit(1)


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

    if zwps_to_cwps:
        logging.info(f"Converting any ZWPS volume of VM '{vm['name']}' to CWPS before starting the migration",
                     to_slack=log_to_slack)
        if not cs.update_zwps_to_cwps(vm['instancename'], 'MCC_v1.CWPS'):
            logging.error(f"Failed to apply CWPS disk offering to VM '{vm['name']}'", to_slack=log_to_slack)
            return False

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

    destination_host = target_cluster.find_migration_host(vm)
    if not destination_host:
        return False

    if dry_run:
        logging.info(
            f"Would migrate '{vm['name']}' to '{destination_host['name']}' on cluster '{target_cluster['name']}'")
        return True

    disk_info = source_host.get_disks(vm)
    for path, disk_info in disk_info.items():
        _, path, _, _, size = cs.get_volume_size(path)

        if int(size) < int(disk_info['size']):
            logging.warning(
                f"Size for '{disk_info['path']}' in DB ({size}) is less than libvirt reports ({disk_info['size']}), updating DB")
            cs.update_volume_size(vm['instancename'], path, disk_info['size'])

    if not vm.migrate(destination_host, with_volume=True):
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
            cs.add_vm_to_affinity_group(vm['instancename'], add_affinity_group)

        logging.info(
            f"VM '{vm['name']}' successfully migrated to '{destination_host['name']}' on cluster '{target_cluster['name']}'")

    return True


if __name__ == '__main__':
    main()

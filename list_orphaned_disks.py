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
import humanfriendly
from tabulate import tabulate

from cosmicops import CosmicOps, logging

orphan_table_headers = [
    'Domain',
    'Account',
    'Name',
    'Cluster',
    'Storage pool',
    'Path',
    'Allocated Size',
    'Real Size',
    'Orphaned'
]

storage_pool_table_headers = [
    'Cluster',
    'Storage pool',
    '# of orphaned disks',
    'Real space used (GB)'
]


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--cluster', '-t', metavar='<cluster>', help='Show only results for this cluster')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('zone')
def main(profile, cluster, zone):
    """Search primary storage pools in ZONE for orphaned disks."""

    click_log.basic_config()

    # Disable dry run so we can connect to hosts to fetch additional data
    co = CosmicOps(profile=profile, dry_run=False)

    if cluster:
        clusters = [co.get_cluster_by_name(cluster, zone)]
    else:
        clusters = co.get_all_clusters(zone)

    if not clusters:
        sys.exit(1)

    storage_pool_table = []
    for cluster in clusters:
        storage_pools = cluster.get_storage_pools()
        random_host = cluster.get_all_hosts().pop()

        for storage_pool in storage_pools:
            orphan_table = []
            used_space = 0

            storage_pool_file_list = storage_pool.get_file_list(random_host)

            orphans = storage_pool.get_orphaned_volumes()
            for orphan in orphans:
                real_size = int(storage_pool_file_list.get(orphan['path'], 0))
                used_space += real_size
                is_orphaned = 'Y' if real_size > 0 else 'N'

                orphan_table.append(
                    [orphan['domain'], orphan['account'], orphan['name'], cluster['name'], storage_pool['name'],
                     orphan['path'],
                     humanfriendly.format_size(orphan['size'], binary=True),
                     humanfriendly.format_size(real_size, binary=True), is_orphaned])

            logging.info(tabulate(orphan_table, headers=orphan_table_headers, tablefmt='pretty'))
            storage_pool_table.append([cluster['name'], storage_pool['name'], len(orphans),
                                       humanfriendly.format_size(used_space, binary=True)])

    logging.info(tabulate(storage_pool_table, headers=storage_pool_table_headers, tablefmt='pretty'))


if __name__ == '__main__':
    main()

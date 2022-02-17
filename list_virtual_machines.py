#!/usr/bin/env python3# Copyright 2020, Schuberg Philis B.V
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
from distutils.version import LooseVersion

import click
import click_log
import click_spinner
import humanfriendly
import logging as log_module
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
@click.option('--profile', '-p', metavar='<name>', required=True,
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--domain', '-d', 'domain_name', metavar='<domain>', help='List VMs in this domain')
@click.option('--cluster', '-t', 'cluster_name', metavar='<cluster>', help='List VMs on this cluster')
@click.option('--pod', 'pod_name', metavar='<pod>', help='List VMs in this pod')
@click.option('--zone', '-z', 'zone_name', metavar='<zone>', help='List VMs in this zone')
@click.option('--filter', '-f', 'keyword_filter', metavar='<keyword>', help='Only show results matching this keyword')
@click.option('--only-routers', is_flag=True, help='Only show routers')
@click.option('--only-routers-to-be-upgraded', is_flag=True, help='List routers that need an upgrade')
@click.option('--no-routers', is_flag=True, help="Don't list routers")
@click.option('--router-nic-count', metavar='<# of NICs>', type=int, help='List routers with this exact amount of NICs')
@click.option('--nic-count-is-minimum', is_flag=True, help='Router NIC count is a minimum value')
@click.option('--nic-count-is-maximum', is_flag=True, help='Router NIC count is a maximum value')
@click.option('--router-max-version', metavar='<version>', help='List routers older than this version')
@click.option('--router-min-version', metavar='<version', help='List routers newer than this version')
@click.option('--project', 'project_name', metavar='<project>', help='List VMs in this project')
@click.option('--only-project', is_flag=True, help='Only show VMs belonging to a project')
@click.option('--ignore-domains', metavar='<list>', default=[],
              help='Comma separated list of domains to skip (--ignore-domains="domain1, domain2")')
@click.option('--calling-credentials', is_flag=True, help='Only list VMs belonging to the calling credentials')
@click.option('--only-summary', is_flag=True, help='Only show summary of results')
@click.option('--no-summary', is_flag=True, help='Hide the summary')
@click.option('--log-file', metavar='<logfile>', help='Write output to file (and to screen)')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
def main(profile, domain_name, cluster_name, pod_name, zone_name, keyword_filter, only_routers,
         only_routers_to_be_upgraded,
         no_routers,
         router_nic_count, nic_count_is_minimum, nic_count_is_maximum, router_max_version, router_min_version,
         project_name, only_project, ignore_domains, calling_credentials, only_summary, no_summary, log_file):
    """List VMs"""

    click_log.basic_config()
    if log_file:
        logger = logging.getLogger()
        logger.addHandler(log_module.FileHandler(log_file))

    if project_name and domain_name:
        logging.error("The project and domain options can't be used together")
        sys.exit(1)

    co = CosmicOps(profile=profile, dry_run=False)

    if ignore_domains:
        ignore_domains = ignore_domains.replace(' ', '').split(',')
        logging.info(f"Ignoring domains: {str(ignore_domains)}")

    if calling_credentials:
        table_headers = [
            'VM',
            'Storage',
            'Template',
            'Memory',
            'Cores',
            'Instance',
            'Host',
            'Domain',
            'Account',
            'Created',
            'LastRebootVersion'
        ]

        table_data = []

        if only_project:
            vms = co.get_all_project_vms(list_all=False)
        else:
            vms = co.get_all_vms(list_all=False)

        with click_spinner.spinner():
            for vm in vms:
                if vm['domain'] in ignore_domains:
                    continue

                storage_size = sum([volume['size'] for volume in vm.get_volumes()])

                project_name = vm.get('project', None)
                vm_account = f"Proj: {project_name}" if project_name else vm['account']

                table_data.append([
                    vm['name'],
                    humanfriendly.format_size(storage_size, binary=True),
                    vm['templatedisplaytext'],
                    humanfriendly.format_size(vm['memory'] * 1024 ** 2, binary=True),
                    vm['cpunumber'],
                    vm['instancename'],
                    vm['hostname'],
                    vm['domain'],
                    vm_account,
                    vm['created'],
                    vm['laststartversion']
                ])

        logging.info(tabulate(table_data, headers=table_headers, tablefmt='pretty'))
        sys.exit(0)

    if domain_name:
        domain = co.get_domain(name=domain_name)
        if domain is None or domain == []:
            logging.error(f"The domain '{str(domain_name)}' could not be found!")
            sys.exit(1)
    else:
        domain = None

    if project_name:
        project = co.get_project(name=project_name)
        if project is None or project == []:
            logging.error(f"The project '{str(project_name)}' could not be found!")
            sys.exit(1)
    else:
        project = None

    if pod_name:
        pod = co.get_pod(name=pod_name)
        if pod is None or pod == []:
            logging.error(f"The pod '{str(pod_name)}' could not be found!")
            sys.exit(1)
    else:
        pod = None

    if zone_name:
        zone = co.get_zone(name=zone_name)
        if zone is None or zone == []:
            logging.error(f"The zone '{str(zone_name)}' could not be found!")
            sys.exit(1)
    else:
        zone = None

    if cluster_name:
        clusters = [co.get_cluster(name=cluster_name)]
        if clusters[0]:
            logging.error(f"The cluster '{str(cluster_name)}' could not be found!")
            sys.exit(1)

    elif pod:
        clusters = co.get_all_clusters(pod=pod)
    elif zone:
        clusters = co.get_all_clusters(zone=zone)
    else:
        clusters = co.get_all_clusters()

    total_host_counter = 0
    total_vm_counter = 0
    total_host_memory = 0
    total_vm_memory = 0
    total_storage = 0
    total_cores = 0

    for cluster in clusters:
        hosts = cluster.get_all_hosts()
        if not hosts:
            logging.warning(f"No hosts found on cluster '{cluster['name']}'")
            continue

        cluster_host_counter = 0
        cluster_vm_counter = 0
        cluster_host_memory = 0
        cluster_vm_memory = 0
        cluster_storage = 0
        cluster_cores = 0

        cluster_table_headers = [
            'VM',
            'Storage',
            'Template',
            'Router nic count',
            'Router version',
            'Memory',
            'Cores',
            'Instance',
            'Host',
            'Domain',
            'Account',
            'Created',
            'LastRebootVersion'
        ]
        cluster_table_data = []

        for host in hosts:
            cluster_host_counter += 1
            cluster_host_memory += host['memorytotal']

            if not only_routers:
                if project or only_project:
                    vms = host.get_all_project_vms(project=project)
                else:
                    vms = host.get_all_vms(domain=domain, keyword_filter=keyword_filter)

                for vm in vms:
                    if vm['domain'] in ignore_domains:
                        continue

                    cluster_vm_counter += 1
                    storage_size = sum([volume['size'] for volume in vm.get_volumes()])

                    cluster_storage += storage_size
                    cluster_vm_memory += vm['memory']
                    cluster_cores += vm['cpunumber']

                    vm_project_name = vm.get('project', None)
                    vm_account = f"Proj: {vm['project']}" if vm_project_name else vm['account']

                    cluster_table_data.append([
                        vm['name'],
                        humanfriendly.format_size(storage_size, binary=True),
                        vm['templatedisplaytext'],
                        '-',
                        '-',
                        humanfriendly.format_size(vm['memory'] * 1024 ** 2, binary=True),
                        vm['cpunumber'],
                        vm['instancename'],
                        vm['hostname'],
                        vm['domain'],
                        vm_account,
                        vm['created'],
                        vm['laststartversion']
                    ])

            if no_routers:
                continue

            if project or only_project:
                routers = host.get_all_project_routers(project=project)
            else:
                routers = host.get_all_routers(domain=domain)

            for router in routers:
                if router['domain'] in ignore_domains:
                    continue

                if router_min_version and LooseVersion(router['version']) < LooseVersion(router_min_version):
                    continue

                if router_max_version and LooseVersion(router['version']) > LooseVersion(router_max_version):
                    continue

                if router_nic_count and nic_count_is_minimum:
                    if router_nic_count > len(router['nic']):
                        continue
                elif router_nic_count and nic_count_is_maximum:
                    if router_nic_count < len(router['nic']):
                        continue
                elif router_nic_count:
                    if router_nic_count != len(router['nic']):
                        continue

                if only_routers_to_be_upgraded and not router['requiresupgrade']:
                    continue

                cluster_vm_counter += 1

                service_offering = co.get_service_offering(id=router['serviceofferingid'], system=True)
                if service_offering:
                    router['memory'] = service_offering['memory']
                    router['cpunumber'] = service_offering['cpunumber']

                    cluster_vm_memory += router['memory']
                    cluster_cores += router['cpunumber']
                else:
                    router['memory'] = 'Unknown'
                    router['cpunumber'] = 'Unknown'

                if router['isredundantrouter']:
                    redundant_state = router['redundantstate']
                elif router['vpcid']:
                    redundant_state = 'VPC'
                else:
                    redundant_state = 'SINGLE'

                if router['vpcid']:
                    network = co.get_vpc(id=router['vpcid'])
                else:
                    network = co.get_network(id=router['guestnetworkid'])

                if network:
                    display_name = network['name']
                else:
                    display_name = router['name']

                display_name = f"{display_name} ({redundant_state.lower()})"

                if router['requiresupgrade']:
                    display_name = f"{display_name} [ReqUpdate!]"

                router_project_name = router.get('project', None)
                router_account = f"Proj: {router['project']}" if router_project_name else router['account']

                cluster_table_data.append([
                    display_name,
                    '-',
                    '-',
                    len(router['nic']),
                    router['version'],
                    humanfriendly.format_size(router['memory'] * 1024 ** 2, binary=True) if router[
                                                                                                'memory'] != 'Unknown' else
                    router['memory'],
                    router['cpunumber'],
                    router['name'],
                    router['hostname'],
                    router['domain'],
                    router_account,
                    router['created'],
                    router['laststartversion']
                ])

        total_host_counter += cluster_host_counter
        total_host_memory += cluster_host_memory
        total_vm_memory += cluster_vm_memory
        total_vm_counter += cluster_vm_counter
        total_storage += cluster_storage
        total_cores += cluster_cores

        if not only_summary:  # pragma: no cover
            logging.info(tabulate(cluster_table_data, headers=cluster_table_headers, tablefmt='pretty'))

        if not no_summary:  # pragma: no cover
            logging.info(f"\nSummary for '{cluster['name']}':")
            logging.info(f"Number of VMs: {cluster_vm_counter}")
            logging.info(f"Number of hosts: {cluster_host_counter}")
            logging.info(
                f"Allocated memory: {humanfriendly.format_size(cluster_vm_memory * 1024 ** 2, binary=True)} / {humanfriendly.format_size(cluster_host_memory, binary=True)}")
            logging.info(f"Allocated cores: {cluster_cores}")
            logging.info(f"Allocated storage: {humanfriendly.format_size(cluster_storage, binary=True)}")

    if not no_summary:  # pragma: no cover
        logging.info('\n==================  Grand Totals ===============')
        logging.info(f"Total number of VMs: {total_vm_counter}")
        logging.info(f"Total number of hosts: {total_host_counter}")
        logging.info(
            f"Total allocated memory: {humanfriendly.format_size(total_vm_memory * 1024 ** 2, binary=True)} / {humanfriendly.format_size(total_host_memory, binary=True)}")
        logging.info(f"Total allocated cores: {total_cores}")
        logging.info(f"Total allocated storage: {humanfriendly.format_size(total_storage, binary=True)}")


if __name__ == '__main__':
    main()

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

from cosmicops import CosmicOps, logging


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--disable', is_flag=True, help='Disable host(s)')
@click.option('--enable', is_flag=True, help='Enable host(s)')
@click.option('--hypervisor', '-h', type=int, help='Hypervisor number')
@click.option('--end', '-e', type=int, help='Hypervisor number to end, requires -h option as start number')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('cluster')
def main(profile, disable, enable, hypervisor, end, dry_run, cluster):
    """Enable or disable a range of hosts in a specific pod."""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Disable/Enable hypervisor'
    logging.slack_title = 'Host'

    if end and end <= hypervisor:
        logging.error(f"--end cannot be equal or smaller then --hypervisor ({end}<={hypervisor})")
        sys.exit(1)

    if (disable or enable) and dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    clstr = co.get_cluster(name=cluster)

    if not clstr or not clstr['name'] == cluster:
        logging.error(f"Could not find cluster :'{cluster}'")
        sys.exit(1)

    # show hosts resource state if not changing something
    if hypervisor and (disable or enable):
        pod = cluster.split('-')[0]
        if not end:
            end = hypervisor
            logging.info(f"Going to change {pod}-hv{hypervisor:02d}")
        else:
            logging.info(f"Going to change {pod}-hv{hypervisor:02d} upto {pod}-hv{end:02d}")

        for hv in range(hypervisor, end + 1):
            hostname = f"{pod}-hv{hv:02d}"
            host = co.get_host(name=hostname)
            if not host:
                logging.warning(f"host {hostname} not found!")
                continue

            if disable and host['resourcestate'] == 'Disabled':
                logging.warning(f"host {hostname} already disabled! Skipping")
                continue

            if enable and host['resourcestate'] == 'Enabled':
                logging.warning(f"host {hostname} already enabled! Skipping")
                continue

            if disable and not host.disable():
                raise RuntimeError(f"Failed to disable host '{hostname}'")
            if enable and not host.enable():
                raise RuntimeError(f"Failed to enable host '{hostname}'")
        logging.info(f"Done!\n")

    hosts = sorted(clstr.get_all_hosts(), key=lambda h: h['name'])
    for host in hosts:
        logging.info(f"Host {host['name']} is {host['resourcestate']}")


if __name__ == '__main__':
    main()

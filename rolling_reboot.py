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
from pathlib import Path

import click
import click_log

from cosmicops import CosmicOps, logging, RebootAction


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--ignore-hosts', metavar='<list>',
              help='Comma separated list of hosts to skip (--ignore-host="host1, host2")')
@click.option('--only-hosts', metavar='<list>',
              help='Comma separated list of hosts to work on (--only-host="host1, host2")')
@click.option('--skip-os-version', metavar='<version>', help='Skips hosts matching the specified OS version')
@click.option('--reboot', 'reboot_action', flag_value=RebootAction.REBOOT, type=RebootAction, default=True,
              help='Reboot the host [default]')
@click.option('--halt', 'reboot_action', flag_value=RebootAction.HALT, type=RebootAction, help='Instead of rebooting, halt the host')
@click.option('--force-reset', 'reboot_action', flag_value=RebootAction.FORCE_RESET, type=RebootAction,
              help='Instead of reboot, force-reset the host')
@click.option('--pxe', 'reboot_action', flag_value=RebootAction.PXE_REBOOT, type=RebootAction,
              help='Reboot the host in pxe mode')
@click.option('--skip-reboot', 'reboot_action', flag_value=RebootAction.SKIP, type=RebootAction, help='Skip rebooting the host')
@click.option('--upgrade-firmware', 'reboot_action', flag_value=RebootAction.UPGRADE_FIRMWARE, type=RebootAction,
              help='Update the HP firmware and reboot')
@click.option('--pre-empty-script', metavar='<script>', help='Script to run on host before starting live migrations')
@click.option('--post-empty-script', metavar='<script>',
              help='Script to run on host after live migrations have completed')
@click.option('--post-reboot-script', metavar='<script>', help='Script to run after host has rebooted')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click.option('--proxy-host', help='Hypervisor the migrate VMS to, after which we migrate them back to origin', required=False)
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('cluster')
def main(profile, ignore_hosts, only_hosts, skip_os_version, reboot_action, pre_empty_script, post_empty_script,
         post_reboot_script, dry_run, proxy_host, cluster):
    """Perform rolling reboot of hosts in CLUSTER"""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Rolling Reboot'
    logging.slack_title = 'Hypervisor'
    logging.instance_name = 'N/A'
    logging.vm_name = 'N/A'
    logging.cluster = cluster

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    cluster = co.get_cluster(name=cluster)
    if not cluster:
        sys.exit(1)

    hosts = cluster.get_all_hosts()
    logging.debug(f"Found hosts: {hosts}")

    if proxy_host:
        proxy_host = co.get_host(name=proxy_host)
        if proxy_host is None:
            logging.info(f"Cannot find proxy host {proxy_host} in Cosmic!")
            sys.exit(1)

        logging.info(f"Using proxy host: migrate ALL VMs to {proxy_host['name']}, then back to origin")
        if not ignore_hosts:
            logging.info(f"Adding proxy host {proxy_host['name']} to ignore list")
            ignore_hosts = proxy_host['name']
        else:
            ignore_hosts += f",{proxy_host['name']}"

    if ignore_hosts:
        ignore_hosts = ignore_hosts.replace(' ', '').split(',')
        logging.info(f"Ignoring hosts: {str(ignore_hosts)}")

        hosts = [h for h in hosts if h['name'] not in ignore_hosts]
    elif only_hosts:
        only_hosts = only_hosts.replace(' ', '').split(',')
        logging.info(f"Only processing hosts: {str(only_hosts)}")
        hosts = [h for h in hosts if h['name'] in only_hosts]

    if skip_os_version:
        logging.info(f"Skipping hosts with OS: {skip_os_version}")
        hosts = [h for h in hosts if skip_os_version not in h['hypervisorversion']]

    hosts.sort(key=itemgetter('name'))

    target_host = None

    for host in hosts:
        logging.slack_value = host['name']
        logging.zone_name = host['zonename']

        logging.info(f"Processing host {host['name']}", log_to_slack)
        for script in filter(None, (pre_empty_script, post_empty_script, post_reboot_script)):
            path = Path(script)
            host.copy_file(str(path), f'/tmp/{path.name}', mode=0o755)

        if pre_empty_script:
            host.execute(f'/tmp/{Path(pre_empty_script).name}', sudo=True, hide_stdout=False, pty=True)

        if host['resourcestate'] != 'Disabled':
            if not host.disable():
                sys.exit(1)

        if host['state'] != 'Up' and not dry_run:
            logging.error(f"Host '{host['name']} is not up (state: '{host['state']}'), aborting", log_to_slack)
            sys.exit(1)

        running_vms = len(host.get_all_vms())
        logging.info(
            f"Found {running_vms} running on host '{host['name']}'. Will now start migrating them to other hosts in the same cluster",
            log_to_slack)

        while True:
            if proxy_host:
                target_host = proxy_host
            (_, _, failed) = host.empty(target=target_host)
            if failed == 0:
                break

            if target_host:
                logging.warning(
                    f"Failed to empty host '{host['name']}' with target '{target_host['name']}', resetting target host and retrying...",
                    log_to_slack)
                target_host = None
            else:
                logging.warning(f"Failed to empty host '{host['name']}', retrying...", log_to_slack)

            time.sleep(5)

        logging.info(f"Host {host['name']} is empty", log_to_slack)

        if post_empty_script:
            host.execute(f'/tmp/{Path(post_empty_script).name}', sudo=True, hide_stdout=False, pty=True)

        if not host.reboot(reboot_action):
            sys.exit(1)

        if reboot_action != RebootAction.SKIP:
            host.wait_until_offline()
            host.wait_until_online()

        if post_reboot_script:
            host.execute(f'/tmp/{Path(post_reboot_script).name}', sudo=True, hide_stdout=False, pty=True)

        if not host.enable():
            sys.exit(1)

        host.wait_for_agent()

        host.restart_vms_with_shutdown_policy()

        if proxy_host:
            logging.info(f"Host '{host['name']}' is now empty (VMs are on proxy host {proxy_host['name']}). "
                         f"Will now migrate VMs back to origin {host['name']}...", log_to_slack)
            while True:
                (_, _, failed) = proxy_host.empty(target=host)
                if failed == 0:
                    break
            proxy_host.restart_vms_with_shutdown_policy()

            logging.info(f"Host '{host['name']}' is done. It should now have the same VMs as before", log_to_slack)

        target_host = host


if __name__ == '__main__':
    main()

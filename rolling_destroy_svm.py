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

import logging
import time
import sys

import click
import click_log
from collections import defaultdict

from cosmicops import CosmicOps


@click.command()
@click.option('--profile', '-p', required=True, help='Name of the CloudMonkey profile containing the credentials')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click.option('--skip-version', metavar='<version>', help='Skips VM matching the specified version')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO")
def main(profile, dry_run, skip_version):
    """Destroy SVM per zone and waits for a new one"""

    click_log.basic_config()

    if dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run)

    svms = co.get_all_systemvms()
    zones = defaultdict(list)
    for svm in svms:
        if skip_version and co.get_host_by_name(svm['name']).get('version') == skip_version:
            continue
        zones[svm['zonename']].append(svm)

    for zone in zones:
        logging.info(f"Processing zone: {zone}")
        for vm in zones[zone]:
            if not vm.destroy():
                sys.exit(1)

            up = {}
            retries = 60
            while len(up) != len(svms) and retries > 0:
                if not dry_run:
                    time.sleep(5)
                systemvms = {x['name']: x for x in co.get_all_systemvms()}
                host_status = {k: co.get_host_by_name(host_name=k) for k in systemvms}
                up = {k: v for k, v in host_status.items() if host_status[k] and host_status[k]['state'] == 'Up'
                      and host_status[k]['resourcestate'] == 'Enabled'}
                retries -= 1
            if retries == 0:
                logging.error("Exceeded retry count waiting for new systemvm")
                sys.exit(1)


if __name__ == '__main__':
    main()

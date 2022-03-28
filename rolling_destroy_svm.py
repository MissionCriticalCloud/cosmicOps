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
import sys
import time
from collections import defaultdict
from datetime import datetime

import click
import click_log

from cosmicops import CosmicOps


@click.command()
@click.option('--profile', '-p', required=True, help='Name of the CloudMonkey profile containing the credentials')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click.option('--skip-version', metavar='<version>', help='Skips VM matching the specified version')
@click.option('--older-then', metavar='<older_then>', help='Destroy all SVMs older then <YYYYMMDD>')
@click.option('--skip-zone', metavar='<skip_zone>', help='Skips zone')
@click.option('--only-zone', metavar='<only_zone>', help='Only zone')
@click.option('--restart-agent', is_flag=True, metavar='<restart_agent>', help='Restart cosmic-agent')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO")
def main(profile, dry_run, skip_version, older_then, skip_zone, only_zone, restart_agent):
    """Destroy SVM per zone and waits for a new one"""

    click_log.basic_config()

    if dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run)
    if older_then:
        older_then = datetime.strptime(f"{older_then}T00:00:00+0200", '%Y%m%dT%H:%M:%S%z')

    svms = co.get_all_systemvms()
    zones = defaultdict(list)
    for svm in svms:
        if only_zone and co.get_host(name=svm['name']).get('zonename') != only_zone:
            continue
        if skip_zone and co.get_host(name=svm['name']).get('zonename') == skip_zone:
            continue
        if skip_version and co.get_host(name=svm['name']).get('version') == skip_version:
            continue
        if older_then and datetime.strptime(svm['created'], '%Y-%m-%dT%H:%M:%S%z') > older_then:
            continue
        zones[svm['zonename']].append(svm)

    for zone in zones:
        logging.info(f"Processing zone: {zone}")
        for vm in zones[zone]:
            if not vm.destroy():
                sys.exit(1)

            up = list()
            down = list(zones[zone])
            retries = 60
            zone_id = vm['zoneid']
            while len(up) < len(zones[zone]) or len(down) > 0:
                if not dry_run:
                    time.sleep(5)

                try:
                    systemvms = {x['name']: x for x in co.get_all_systemvms(zoneid=zone_id)}
                    host_status = {k: co.get_host(name=k) for k in systemvms}
                    up = list(filter(lambda x: x and x['state'] == 'Up' and x['resourcestate'] == 'Enabled', host_status.values()))
                    down = list(filter(lambda x: x and x['state'] != 'Up' and x['resourcestate'] == 'Enabled', host_status.values()))
                    retries -= 1
                    if retries == 0:
                        break
                    if down and restart_agent:
                        for d in down:
                            svm_object = list(filter(lambda x: x and x['name'].lower() == d['name'], systemvms.values()))[0]
                            svm_object.restart_agent()
                except KeyError:
                    # Ignore keyerror, systemvm is still not available as host
                    pass

            if retries == 0:
                logging.error("Exceeded retry count waiting for new systemvm")
                sys.exit(1)


if __name__ == '__main__':
    main()

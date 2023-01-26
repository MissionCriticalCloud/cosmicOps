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
import re

import click
import click_log

from datetime import datetime

from cosmicops import logging, CosmicOps
from cosmicops.objects import CosmicResourceType


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--older-date', required=True, type=click.DateTime(formats=["%d-%m-%Y"]), help='All templates older than this date will be removed')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
def main(profile, older_date, dry_run):
    """Cleanup old templates"""

    click_log.basic_config()
    if dry_run:
        logging.info('Running in dry-run mode, will only show changes')

    logging.info('Getting all templates...\n\n')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=False, timeout=300)
    templates = co.get_all_templates()

    # Destroy template older than date
    logging.info(f"Deleting all templates older than {older_date.date()}\n\n")
    for template in templates:
        if 'created' not in template:
            logging.warning(f"Field 'created' not found in template '{template['name']}'")
            continue
        if 'domain' not in template:
            logging.warning(f"Field 'domain' not found in template '{template['name']}'")
            continue
        logging.debug(f"Template: '{template['name']}' created on '{template['created']}'")
        if template['domain'] == 'ROOT':
            template_date = datetime.strptime(template['created'], '%Y-%m-%dT%H:%M:%S%z')
            logging.debug(f"Timestamp template {template_date.timestamp()} < {older_date.timestamp()}")
            if template_date.timestamp() < older_date.timestamp():
                template.delete()
    sys.exit(0)


if __name__ == '__main__':
    main()

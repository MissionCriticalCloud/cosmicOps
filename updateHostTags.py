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

import click
import click_log

from cosmicops import CosmicOps, logging


@click.command()
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--host', required=True, help='Host to add/remove tags')
@click.option('--tags', required=True, help='Tags to add/remove (comma separated)')
@click.option('--add/--del', is_flag=True, default=True, help='Add/Remove tags  [default: add]')
@click.option('--dry-run/--exec', is_flag=True, default=True, help='Enable/disable dry-run  [default: dry-run]')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
def main(profile, host, tags, add, dry_run):
    """Add/Remove tags from HOST"""
    click_log.basic_config()

    tags = tags.split(',')

    if dry_run:
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=False)
    co_host = co.get_host(name=host)
    if co_host:
        co_host.update_tags(hosttags=tags, add=add)
    else:
        logging.warning(f"Host '{host}' not found")


if __name__ == '__main__':
    main()

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

from cosmicops import logging
from cosmicops.list_orphaned_disks import list_orphaned_disks


@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--cluster', '-t', metavar='<cluster>', help='Show only results for this cluster')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('zone')
def main(profile, cluster, zone):
    """Search primary storage pools in ZONE for orphaned disks."""

    click_log.basic_config()

    logging.info(list_orphaned_disks(profile, cluster, zone))


if __name__ == '__main__':
    main()

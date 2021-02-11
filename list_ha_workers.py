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
from cosmicops.list_ha_workers import list_ha_workers


@click.command()
@click.option('--profile', '-p', metavar='<name>', help='Name of the configuration profile containing the credentials')
@click.option('--hostname', '-n', metavar='<hostname>', default='', help='Show only works on this host')
@click.option('--name-filter', metavar='<vm name>', help='Filter on specified VM name')
@click.option('--non-running', is_flag=True, help='Only show entries with a non-running state')
@click.option('--plain-display', is_flag=True, help='Plain text output, no pretty tables')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
def main(profile, hostname, name_filter, non_running, plain_display):
    """Lists HA workers"""

    click_log.basic_config()

    logging.info(list_ha_workers(profile, hostname, name_filter, non_running, plain_display))


if __name__ == '__main__':
    main()

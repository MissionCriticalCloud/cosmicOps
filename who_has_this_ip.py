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

from cosmicops import logging
from cosmicops.who_has_this_ip import who_has_this_ip


@click.command()
@click.option('--profile', '-p', metavar='<name>', help='Name of the configuration profile containing the credentials')
@click.option('--all-databases', '-a', is_flag=True, help='Search through all configured databases')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('ip_address')
def main(profile, all_databases, ip_address):
    """Shows who uses IP_ADDRESS"""

    click_log.basic_config()

    if not (profile or all_databases):
        logging.error("You must specify --profile or --all-databases")
        sys.exit(1)

    if profile and all_databases:
        logging.error("The --profile and --all-databases options can't be used together")
        sys.exit(1)

    try:
        result = who_has_this_ip(profile, all_databases, ip_address)
    except RuntimeError as err:
        logging.error(err)
        sys.exit(1)

    logging.info(result)


if __name__ == '__main__':
    main()

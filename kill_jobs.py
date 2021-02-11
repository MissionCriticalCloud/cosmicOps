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
from cosmicops.kill_jobs import kill_jobs


@click.command()
@click.option('--profile', '-p', metavar='<name>', help='Name of the configuration profile containing the credentials')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('instance_id')
def main(profile, dry_run, instance_id):
    """Kills all jobs related to INSTANCE_ID"""

    click_log.basic_config()

    if dry_run:
        logging.warning('Running in dry-run mode, will only show changes')

    kill_jobs(profile, dry_run, instance_id)


if __name__ == '__main__':
    main()

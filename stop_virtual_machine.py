#!/usr/bin/env python3
# Copyright 2022, Schuberg Philis B.V
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
@click.option('--profile', '-p', default='config', help='Name of the CloudMonkey profile containing the credentials')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click.option('--is-project-vm', is_flag=True, help='The specified VM is a project VM')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
@click.argument('vm')
def main(profile, dry_run, vm, is_project_vm):
    """Stop VM"""

    click_log.basic_config()

    log_to_slack = True
    logging.task = 'Stop a virtual machine'
    logging.slack_title = 'Domain'

    if dry_run:
        log_to_slack = False
        logging.warning('Running in dry-run mode, will only show changes')

    co = CosmicOps(profile=profile, dry_run=dry_run, log_to_slack=log_to_slack)

    vm_instance = co.get_vm(name=vm, is_project_vm=is_project_vm)

    if not vm_instance:
        sys.exit(1)

    if vm_instance['state'] == 'Stopped':
        logging.warning(f"Cannot stop, VM already stopped")
        sys.exit(0)

    if not vm_instance['state'] == 'Running':
        logging.warning(f"Cannot stop, VM has has state: '{vm_instance['state']}'")
        sys.exit(1)

    if not vm_instance.stop():
        sys.exit(1)


if __name__ == '__main__':
    main()

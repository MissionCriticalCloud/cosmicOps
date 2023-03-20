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

from cosmicops import logging, CosmicOps
from cosmicops.objects import CosmicResourceType

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

@click.command()
@click.option('--profile', '-p', metavar='<name>', default='config',
              help='Name of the CloudMonkey profile containing the credentials')
@click.option('--skip-name', metavar='<skip_name>', default=None, help='Skips name (regex)')
@click.option('--employee-only', is_flag=True, metavar='<employee_only>', default=False, help='List only employees')
@click.option('--dry-run/--exec', is_flag=True, default=True, show_default=True, help='Enable/disable dry-run')
@click_log.simple_verbosity_option(logging.getLogger(), default="INFO", show_default=True)
def main(profile, skip_name, employee_only, dry_run):
    """Cleanup empty tenants"""

    click_log.basic_config()

    # Email template
    template = Template(open('email_template.html').read())

    logging.info('Getting all accounts...\n\n')

    regex = None
    if skip_name:
        regex = re.compile(skip_name)
    co = CosmicOps(profile=profile, log_to_slack=False, timeout=300)
    accounts = co.get_all_accounts()

    # Disable accounts with no VM's
    print(f"=== Resources per account in {profile} ===\n")
    for account in accounts:
        if account['domain'] == 'ROOT' or (regex and regex.match(account['name'])):
            continue
        domain = co.get_domain(id=account['domainid'])
        if employee_only and domain['parentdomainname'] != 'Employee':
            continue
        users = co.get_all_users(account=account['name'], domainid=account['domainid'], accounttype=2)
        if len(users) > 0:
            # print(f"\n{profile.upper()} - Domain: {domain['name']} - {users[0]['email'].lower()}")

            resource_text = ""
            mail_needed = False

            resources = domain.get_resourcecount()
            for item in CosmicResourceType:
                if resources[item.name] > 0:
                    resource_text += f"<tr><td>{item.name}</td><td>{resources[item.name]}</td></tr>\n"
                    if item.name == 'VMS' and resources[item.name] > 0:
                        vms = co.get_all_vms(account=account['name'], domainid=account['domainid'])
                        for vm in vms:
                            if vm['state'] == 'Stopped':
                                resource_text += f"<tr><td></td><td>VM '{vm['name']}' is stopped</td></tr>\n"
                                mail_needed = True

                    if item.name == 'PRI_STORAGE' and resources[item.name] > 0:
                        volumes = co.get_all_volumes(account=account['name'], domainid=account['domainid'])
                        for volume in volumes:
                            vmid = volume.get('virtualmachineid', None)
                            if not vmid:
                                resource_text += f"<tr><td></td><td>Disk '{volume['name']}' is not attached</td></tr>\n"
                                mail_needed = True

            if mail_needed:
                email_text = template.render(
                    firstname=users[0]['firstname'],
                    resource_text=resource_text,
                    zone=profile.upper()
                )
                print(email_text)
                if dry_run:
                    continue

                # # Email content
                email = MIMEMultipart()
                email['From'] = 'mcc@schubergphilis.com'
                # email['To'] = users[0]['email'].lower()
                email['To'] = users[0]['email'].lower()
                email['Subject'] = f"Your resources in MCC { profile.upper() }"
                email.attach(MIMEText(email_text, 'html'))

                # # Send email
                smtp_server = '127.0.0.1'
                smtp_port = 25
                smtp_connection = smtplib.SMTP(smtp_server, smtp_port)
                smtp_connection.sendmail(
                    from_addr='mcc@schubergphilis.com',
                    to_addrs=users[0]['email'].lower(),
                    msg=email.as_string())
                smtp_connection.quit()

    sys.exit(0)


if __name__ == '__main__':
    main()

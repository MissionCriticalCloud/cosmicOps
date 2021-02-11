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

from tabulate import tabulate

from cosmicops import CosmicSQL


def who_has_this_mac(profile, all_databases, mac_address):
    if all_databases:
        databases = CosmicSQL.get_all_dbs_from_config()
        if not databases:
            raise RuntimeError("No databases found in configuration file")
    else:
        databases = [profile]

    table_headers = [
        "VM",
        "Network",
        "MAC address",
        "IPv4",
        "Netmask",
        "Mode",
        "State",
        "Created"
    ]
    table_data = []

    for database in databases:
        cs = CosmicSQL(server=database, dry_run=False)

        for (network_name, mac_address, ipv4_address, netmask, _, mode, state, created, vm_name) \
                in cs.get_mac_address_data(mac_address):
            table_data.append([vm_name, network_name, mac_address, ipv4_address, netmask, mode, state, created])

    return tabulate(table_data, headers=table_headers, tablefmt='pretty')

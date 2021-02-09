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

from cosmicops import CosmicOps, RebootAction


def empty_host(profile, shutdown, dry_run, host):
    co = CosmicOps(profile=profile, dry_run=dry_run)

    host = co.get_host(name=host)
    if not host:
        raise RuntimeError(f"Host '{host['name']}' not found")

    (total, success, failed) = host.empty()
    result_message = f"Result: {success} successful, {failed} failed out of {total} total VMs"

    if not failed and shutdown:
        host.set_uid_led(True)
        if not host.reboot(RebootAction.HALT):
            raise RuntimeError(f"Failed to shutdown host '{host['name']}'")
        host.wait_until_offline()
        result_message = f"{result_message}\nHost '{host['name']}' has shutdown, UID led is turned on"
    elif failed and shutdown:
        result_message = f"{result_message}\nNot shutting down host '{host['name']}' because migration completed with failed VMs"

    return result_message

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
from enum import Enum


class CosmicResourceType(Enum):
    # 0 - Instance. Number of instances a user can create.
    VMS = 0
    # 1 - IP.Number; of; public; IP; addresses; a; user; can; own.
    IPS = 1
    # 2 - Volume.Number; of; disk; volumes; a; user; can; create.
    VOLUMES = 2
    # 3 - Snapshot.Number; of; snapshots; a; user; can; create.
    SNAPSHOTS = 3
    # 4 - Template.Number; of; templates; that; a; user; can; register / create.
    TEMPLATES = 4
    # 5 - Project.Number; of; projects; that; a; user; can; create.
    PROJECTS = 5
    # 6 - Network.Number; of; guest; network; a; user; can; create.
    NETWORKS = 6
    # 7 - VPC.Number; of; VPC; a; user; can; create.
    VPCS = 7
    # 8 - CPU.Total; number; of; CPU; cores; a; user; can; use.
    CPUS = 8
    # 9 - Memory.Total; Memory( in MB) a; user; can; use.
    MEMORY = 9
    # 10 - PrimaryStorage.Total; primary; storage; space( in GiB) a; user; can; use.
    PRI_STORAGE = 10
    # 11 - SecondaryStorage.Total; secondary; storage; space( in GiB) a; user; can; use.
    SEC_STORAGE = 11
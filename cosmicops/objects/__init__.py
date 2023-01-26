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

from .account import CosmicAccount
from .cluster import CosmicCluster
from .domain import CosmicDomain
from .host import CosmicHost
from .network import CosmicNetwork
from .pod import CosmicPod
from .project import CosmicProject
from .resourcetype import CosmicResourceType
from .router import CosmicRouter
from .template import CosmicTemplate
from .serviceoffering import CosmicServiceOffering
from .storagepool import CosmicStoragePool
from .systemvm import CosmicSystemVM
from .vm import CosmicVM
from .volume import CosmicVolume
from .vpc import CosmicVPC
from .zone import CosmicZone

__all__ = [
    CosmicAccount,
    CosmicCluster,
    CosmicDomain,
    CosmicHost,
    CosmicNetwork,
    CosmicPod,
    CosmicProject,
    CosmicResourceType,
    CosmicRouter,
    CosmicTemplate,
    CosmicServiceOffering,
    CosmicStoragePool,
    CosmicSystemVM,
    CosmicVM,
    CosmicVolume,
    CosmicVPC,
    CosmicZone
]

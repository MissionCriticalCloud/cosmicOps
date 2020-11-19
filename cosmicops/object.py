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
from collections.abc import Mapping


class CosmicObject(Mapping):
    def __init__(self, ops, data):
        self._ops = ops
        self._data = data
        self.dry_run = ops.dry_run
        self.log_to_slack = ops.log_to_slack

    def __getitem__(self, item):
        return self._data[item]

    def __setitem__(self, item, value):
        self._data[item] = value

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

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

from unittest import TestCase
from unittest.mock import patch

from click.testing import CliRunner

import list_ha_workers


class TestListHAWorkers(TestCase):
    def setUp(self):
        cs_patcher = patch('list_ha_workers.CosmicSQL')
        self.cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.cs.return_value
        self.runner = CliRunner()

    def test_main(self):
        result = self.runner.invoke(list_ha_workers.main, ['-s', 'server_address', '-p', 'password'])
        self.cs.assert_called_with(server='server_address', database='cloud', port=3306, user='cloud',
                                   password='password', dry_run=False)
        self.cs_instance.list_ha_workers.assert_called_with('')
        self.assertEqual(0, result.exit_code)

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

import kill_jobs


class TestKillJobs(TestCase):
    def setUp(self):
        cs_patcher = patch('cosmicops.kill_jobs.CosmicSQL')
        self.cs = cs_patcher.start()
        self.addCleanup(cs_patcher.stop)
        self.cs_instance = self.cs.return_value
        self.runner = CliRunner()

    def test_main(self):
        result = self.runner.invoke(kill_jobs.main, ['--exec', '-p', 'profile', '1'])
        self.cs.assert_called_with(server='profile', dry_run=False)
        self.cs_instance.kill_jobs_of_instance.assert_called_with('1')
        self.assertEqual(0, result.exit_code)

    def test_dry_run(self):
        result = self.runner.invoke(kill_jobs.main, ['-p', 'profile', '1'])
        self.cs.assert_called_with(server='profile', dry_run=True)

        self.assertEqual(0, result.exit_code)

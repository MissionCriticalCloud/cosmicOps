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

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from testfixtures import tempdir

from cosmicops import get_config


class TestCosmicSQL(TestCase):
    @tempdir()
    def test_get_config_file(self, tmp):
        config_data = (b"[test_local_dir]\n"
                       b"dummy = local\n"
                       )
        tmp.write('config', config_data)
        with patch('pathlib.Path.cwd') as path_cwd_mock:
            path_cwd_mock.return_value = Path(tmp.path)
            config = get_config()

        self.assertIn('test_local_dir', config)
        self.assertIn('dummy', config['test_local_dir'])
        self.assertEqual('local', config['test_local_dir']['dummy'])

    @tempdir()
    def test_get_config_file_fallback(self, tmp):
        config_data = (b"[test_home_dir]\n"
                       b"dummy = home\n"
                       )
        tmp.makedir('.cosmicops')
        tmp.write('.cosmicops/config', config_data)
        with patch('pathlib.Path.home') as path_home_mock:
            with patch('pathlib.Path.cwd') as path_cwd_mock:
                path_cwd_mock.return_value = Path(tmp.path)
                path_home_mock.return_value = Path(tmp.path)

                config = get_config()

        self.assertIn('test_home_dir', config)
        self.assertIn('dummy', config['test_home_dir'])
        self.assertEqual('home', config['test_home_dir']['dummy'])

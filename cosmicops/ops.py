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

import logging
import time
from configparser import ConfigParser
from pathlib import Path

import click_spinner
from cs import CloudStack, CloudStackException
from requests.exceptions import ConnectionError

from .cluster import CosmicCluster
from .host import CosmicHost
from .systemvm import CosmicSystemVM


def load_cloud_monkey_profile(profile):
    config_file = Path.home() / '.cloudmonkey' / 'config'
    config = ConfigParser()
    config.read(str(config_file))
    logging.debug(f"Loading profile '{profile}' from config '{config_file}'")

    if profile == 'config':
        profile = config['core']['profile']

    return config[profile]['url'], config[profile]['apikey'], config[profile]['secretkey']


class CosmicOps(object):
    def __init__(self, endpoint=None, key=None, secret=None, profile=None, timeout=60, dry_run=False):
        if profile:
            (endpoint, key, secret) = load_cloud_monkey_profile(profile)

        self.endpoint = endpoint
        self.key = key
        self.secret = secret

        self.timeout = timeout
        self.dry_run = dry_run
        self.cs = CloudStack(self.endpoint, self.key, self.secret, self.timeout)

    def get_host_by_name(self, host_name):
        response = self.cs.listHosts(name=host_name).get('host')

        if not response:
            logging.error(f"Host '{host_name}' not found")
            return None
        elif len(response) != 1:
            logging.error(f"Lookup for host '{host_name}' returned multiple results")
            return None

        return CosmicHost(self, response[0])

    def get_host_json_by_id(self, host_id):
        return self.cs.listHosts(id=host_id).get('host')

    def get_cluster_by_name(self, cluster_name):
        response = self.cs.listClusters(name=cluster_name).get('cluster')

        if not response:
            logging.error(f"Cluster '{cluster_name}' not found")
            return None
        elif len(response) != 1:
            logging.error(f"Lookup for cluster '{cluster_name}' returned multiple results")
            return None

        return CosmicCluster(self, response[0])

    def get_systemvm_by_name(self, systemvm_name):
        response = self.cs.listSystemVms(name=systemvm_name).get('systemvm')

        if not response:
            logging.error(f"System VM '{systemvm_name}' not found")
            return None
        elif len(response) != 1:
            logging.error(f"Lookup for system VM '{systemvm_name}' returned multiple results")
            return None

        return CosmicSystemVM(self, response[0])

    def get_systemvm_by_id(self, systemvm_id):
        response = self.cs.listSystemVms(id=systemvm_id).get('systemvm')

        if not response:
            logging.error(f"System VM with ID '{systemvm_id}' not found")
            return None
        elif len(response) != 1:
            logging.error(f"Lookup for system VM with ID '{systemvm_id}' returned multiple results")
            return None

        return CosmicSystemVM(self, response[0])

    def wait_for_job(self, job_id, retries=10):
        job_status = 0

        with click_spinner.spinner():
            while True:
                if retries <= 0:
                    break

                try:
                    job_status = self.cs.queryAsyncJobResult(jobid=job_id).get('jobstatus', 0)
                except CloudStackException as e:
                    if 'multiple JSON fields named jobstatus' not in str(e):
                        raise e
                    logging.debug(e)
                    retries -= 1
                except ConnectionError as e:
                    if 'Connection aborted' not in str(e):
                        raise e
                    logging.debug(e)
                    retries -= 1

                if int(job_status) == 1:
                    return True
                elif int(job_status) == 2:
                    break

                time.sleep(1)

        return False

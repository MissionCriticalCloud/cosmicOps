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
import itertools
import time
from configparser import ConfigParser
from pathlib import Path

import click_spinner
from cs import CloudStack, CloudStackException
from requests.exceptions import ConnectionError

from cosmicops.objects import CosmicCluster, CosmicDomain, CosmicHost, CosmicNetwork, CosmicPod, CosmicProject, \
    CosmicRouter, CosmicServiceOffering, CosmicStoragePool, CosmicSystemVM, CosmicVM, CosmicVolume, CosmicVPC, \
    CosmicZone
from .log import logging


def _load_cloud_monkey_profile(profile):
    config_file = Path.home() / '.cloudmonkey' / 'config'
    config = ConfigParser()
    config.read(str(config_file))
    logging.debug(f"Loading profile '{profile}' from config '{config_file}'")

    if profile == 'config':
        profile = config['core']['profile']

    return config[profile]['url'], config[profile]['apikey'], config[profile]['secretkey']


class CosmicOps(object):
    spinner = itertools.cycle(['-', '\\', '|', '/'])

    def __init__(self, endpoint=None, key=None, secret=None, profile=None, timeout=60, dry_run=True,
                 log_to_slack=False):
        if profile:
            (endpoint, key, secret) = _load_cloud_monkey_profile(profile)

        self.endpoint = endpoint
        self.key = key
        self.secret = secret
        self.timeout = timeout
        self.dry_run = dry_run
        self.log_to_slack = log_to_slack
        self.cs = CloudStack(self.endpoint, self.key, self.secret, self.timeout)

    def _cs_get_single_result(self, list_function, kwargs, cosmic_object, cs_type, pretty_name=None, json=False):
        func = getattr(self.cs, list_function, None)
        if not func:  # pragma: no cover
            logging.error(f"Unknown list function '{list_function}'")
            return None

        if not pretty_name:
            pretty_name = cs_type

        if 'json' in kwargs:
            json = True
            del kwargs['json']

        response = func(fetch_list=True, **kwargs)

        if not response:
            logging.error(f"{pretty_name.capitalize()} with attributes {kwargs} not found")
            return None
        elif len(response) != 1:
            logging.error(f"Lookup for {pretty_name} with attributes {kwargs} returned multiple results")
            return None

        return response[0] if json else cosmic_object(self, response[0])

    def _cs_get_all_results(self, list_function, kwargs, cosmic_object, cs_type):
        func = getattr(self.cs, list_function, None)
        if not func:  # pragma: no cover
            logging.error(f"Unknown list function '{list_function}'")
            return None

        response = func(fetch_list=True, **kwargs)

        return [cosmic_object(self, item) for item in response]

    def get_host(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listHosts', kwargs, CosmicHost, 'host')

    def get_volume(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listVolumes', kwargs, CosmicVolume, 'volume')

    def get_project(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listProjects', kwargs, CosmicProject, 'project')

    def get_zone(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listZones', kwargs, CosmicZone, 'zone')

    def get_pod(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listPods', kwargs, CosmicPod, 'pod')

    def get_system_vm(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listSystemVms', kwargs, CosmicSystemVM, 'systemvm', 'system VM')

    def get_domain(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listDomains', kwargs, CosmicDomain, 'domain')

    def get_network(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listNetworks', kwargs, CosmicNetwork, 'network')

    def get_vpc(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listVPCs', kwargs, CosmicVPC, 'vpc', 'VPC')

    def get_storage_pool(self, **kwargs):  # pragma: no cover
        return self._cs_get_single_result('listStoragePools', kwargs, CosmicStoragePool, 'storagepool', 'storage pool')

    def get_vm(self, is_project_vm=False, **kwargs):
        if 'name' in kwargs:
            kwargs['listall'] = True

            if kwargs['name'].startswith('i-'):
                kwargs['keyword'] = kwargs['name']
                del kwargs['name']

        if is_project_vm:
            kwargs['projectid'] = '-1'

        return self._cs_get_single_result('listVirtualMachines', kwargs, CosmicVM, 'virtualmachine', 'VM')

    def get_project_vm(self, **kwargs):
        return self.get_vm(is_project_vm=True, **kwargs)

    def get_router(self, is_project_router=False, **kwargs):
        if 'name' in kwargs:
            kwargs['listall'] = True

        if is_project_router:
            kwargs['projectid'] = '-1'

        return self._cs_get_single_result('listRouters', kwargs, CosmicRouter, 'router')

    def get_cluster(self, zone=None, **kwargs):
        if zone:
            zone = self.get_zone(name=zone)
            if not zone:
                return None

            kwargs['zoneid'] = zone['id']

        return self._cs_get_single_result('listClusters', kwargs, CosmicCluster, 'cluster')

    def get_service_offering(self, system=False, **kwargs):
        if 'issystem' not in kwargs and system:
            kwargs['issystem'] = system

        return self._cs_get_single_result('listServiceOfferings', kwargs, CosmicServiceOffering, 'serviceoffering',
                                          'service offering')

    def get_all_systemvms(self, **kwargs):  # pragma: no cover
        return self._cs_get_all_results('listSystemVms', kwargs, CosmicSystemVM, 'systemvm')

    def get_all_clusters(self, zone=None, pod=None, **kwargs):
        if 'zoneid' not in kwargs and zone:
            kwargs['zoneid'] = zone['id']
        if 'podid' not in kwargs and pod:
            kwargs['podid'] = pod['id']

        return self._cs_get_all_results('listClusters', kwargs, CosmicCluster, 'cluster')

    def get_all_vms(self, list_all=True, **kwargs):
        if 'listall' not in kwargs:
            kwargs['listall'] = list_all

        return self._cs_get_all_results('listVirtualMachines', kwargs, CosmicVM, 'virtualmachine')

    def get_all_storage_pools(self, list_all=True, **kwargs):
        return self._cs_get_all_results('listStoragePools', kwargs, CosmicStoragePool, 'storagepool')

    def get_all_project_vms(self, list_all=True, **kwargs):
        kwargs['projectid'] = '-1'
        return self.get_all_vms(list_all=list_all, **kwargs)

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

    def wait_for_vm_migration_job(self, job_id, retries=10, domjobinfo=True, source_host=None, instancename=None):
        status = False
        job_status = 0
        prev_percentage = 0.

        while True:
            if domjobinfo and source_host and instancename:
                djstats = source_host.get_domjobstats(instancename)
                cur_percentage = float(djstats.dataProcessed / (djstats.dataTotal or 1) * 100)
                if cur_percentage > prev_percentage:
                    prev_percentage = cur_percentage
                print("%4.f%% " % prev_percentage, flush=True, end='')
            print("%s" % next(self.spinner), flush=True, end='\r')

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
                status = True
                break
            elif int(job_status) == 2:
                break

            time.sleep(1)

        if domjobinfo and source_host and instancename and int(job_status) == 0:
            print("100%         ")
        else:
            print()
        return status

    def wait_for_volume_migration_job(self, volume_id, job_id, blkjobinfo=True, source_host=None, vm=None, vol=None):
        prev_percentage = 0.

        # Hack to wait for job to start
        time.sleep(60)
        while True:
            if blkjobinfo and source_host and vm and vol:
                blkjobinfo = source_host.get_blkjobinfo(vm, vol)
                cur_percentage = float(blkjobinfo.current / (blkjobinfo.end or 1) * 100)
                if cur_percentage > prev_percentage:
                    prev_percentage = cur_percentage
                print("%4.f%% " % prev_percentage, flush=True, end='')
            print("%s" % next(self.spinner), flush=True, end='\r')

            volume = self.get_volume(id=volume_id, json=True)
            if volume is None:
                logging.error(f"Error: Could not find volume '{volume_id}'")
                return False

            if volume['state'] == "Ready":
                break
            time.sleep(1)
            logging.debug(f"Volume '{volume_id}' is in {volume['state']} state and not Ready. Sleeping.")
        # Return result of job
        status = self.wait_for_job(job_id=job_id, retries=1)
        if blkjobinfo and source_host and vm and vol and status:
            print("100%       ")
        else:
            print()
        return status

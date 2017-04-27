from __future__ import print_function, unicode_literals

import os

import requests
import sys

from colorclass import Color
from packaging import version
from pip.locations import site_config_files

try:
    from configparser import ConfigParser
except ImportError:   # pragma: nocover
    from ConfigParser import ConfigParser, NoOptionError


class PackagesStatusDetector(object):
    packages = []
    packages_status_map = {}
    PYPI_API_URL = None
    pip_config_locations = [
        '~/.pip/pip.conf',
        '~/.pip/pip.ini',
        'pip.test.conf',  # for testing
        '~/.config/pip/pip.conf',
        '~/.config/pip/pip.ini',
    ]

    def __init__(self, packages, use_default_index=False):
        self.packages = packages
        self.packages_status_map = {}
        self.PYPI_API_URL = 'https://pypi.python.org/pypi/{package}/json'

        if not use_default_index:
            self._update_index_url_from_configs()

    def _update_index_url_from_configs(self):
        """ Checks for alternative index-url in pip.conf """

        if 'VIRTUAL_ENV' in os.environ:
            self.pip_config_locations.append(os.path.join(os.environ['VIRTUAL_ENV'], 'pip.conf'))
            self.pip_config_locations.append(os.path.join(os.environ['VIRTUAL_ENV'], 'pip.ini'))

        if site_config_files:
            self.pip_config_locations.extend(site_config_files)

        index_url = None
        custom_config = None
        for pip_config_filename in self.pip_config_locations:
            if pip_config_filename.startswith('~'):
                pip_config_filename = os.path.expanduser(pip_config_filename)

            if os.path.isfile(pip_config_filename):
                config = ConfigParser()
                config.read([pip_config_filename])
                try:
                    index_url = config.get('global', 'index-url')
                    custom_config = pip_config_filename
                    break  # stop on first detected, because config locations have a priority
                except NoOptionError:  # pragma: nocover
                    pass

        if index_url:
            self.PYPI_API_URL = self._prepare_api_url(index_url)
            print(Color('Setting API url to {{autoyellow}}{}{{/autoyellow}} as found in {{autoyellow}}{}{{/autoyellow}}'
                        '. Use --default-index-url to use pypi default index'.format(self.PYPI_API_URL, custom_config)))

    @staticmethod
    def _prepare_api_url(index_url):  # pragma: nocover
        if '/pypi/' in index_url:
            base_url = index_url.split('/pypi/')[0]
            return '{}/pypi/{{package}}/json'.format(base_url)

        if '/simple' in index_url:
            base_url = index_url.split('/simple/')[0]
            return '{}/pypi/{{package}}/json'.format(base_url)

        if '/+simple' in index_url:
            base_url = index_url.split('/+simple')[0]
            return '{}/pypi/{{package}}/json'.format(base_url)

        base_url = index_url.rstrip('/')
        return '{}/pypi/{{package}}/json'.format(base_url)

    def detect_available_upgrades(self, options):
        prerelease = options.get('--prerelease', False)
        explicit_packages_lower = None
        if options['-p'] and options['-p'] != ['all']:
            explicit_packages_lower = [pack_name.lower() for pack_name in options['-p']]

        for i, package in enumerate(self.packages):

            package_name, pinned_version = self._expand_package(package)
            if not package_name or not pinned_version:  # pragma: nocover
                # todo: treat <= or >= instead of ==
                continue

            if explicit_packages_lower and package_name.lower() not in explicit_packages_lower:
                # skip if explicit and not chosen
                continue

            current_version = version.parse(pinned_version)

            if pinned_version and isinstance(current_version, version.Version):  # version parsing is correct
                print('{}/{}: {} ... '.format(i + 1, len(self.packages), package_name), end='')
                sys.stdout.flush()

                # query for upgrade available
                response = requests.get(self.PYPI_API_URL.format(package=package_name))

                if not response.ok:  # pragma: nocover
                    print('pypi API error: {}'.format(response.reason))
                    continue
                data = response.json()
                # latest_stable_version = version.parse(data['info']['version'])
                all_versions = [version.parse(vers) for vers in data['releases'].keys()]
                latest_version = max([vers for vers in all_versions
                                      if not vers.is_prerelease and not vers.is_postrelease])

                # even if user did not choose prerelease, if the package from requirements is pre/post release, use it
                if prerelease or current_version.is_postrelease or current_version.is_prerelease:
                    prerelease_versions = [vers for vers in all_versions if vers.is_prerelease or vers.is_postrelease]
                    if prerelease_versions:
                        latest_version = max(prerelease_versions)
                try:
                    try:
                        latest_version_info = data['releases'][str(latest_version)][0]
                    except KeyError:  # pragma: nocover
                        # non-RFC versions, get the latest from pypi response
                        latest_version = version.parse(data['info']['version'])
                        latest_version_info = data['releases'][str(latest_version)][0]
                except Exception:  # pragma: nocover
                    print('error while parsing version')
                    continue

                upload_time = latest_version_info['upload_time'].replace('T', ' ')

                # compare versions
                if current_version < latest_version:
                    print('upgrade available: {} ==> {} (uploaded on {})'.format(current_version,
                                                                                 latest_version,
                                                                                 upload_time))
                else:
                    print('up to date: {}'.format(current_version))
                sys.stdout.flush()

                self.packages_status_map[package_name] = {
                    'name': package_name,
                    'current_version': current_version,
                    'latest_version': latest_version,
                    'upgrade_available': current_version < latest_version,
                    'upload_time': upload_time
                }

        return self.packages_status_map

    def _expand_package(self, package_line):
        if '==' in package_line:
            name, vers = package_line.split('==')

            if '[' in name and name.strip().endswith(']'):
                name = name.split('[')[0]

            return name, vers

        return None, None

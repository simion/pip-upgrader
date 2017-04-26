from __future__ import print_function

import requests
import sys
from packaging import version


class PackagesStatusDetector(object):
    packages = []
    packages_status_map = {}

    PYPI_API_URL = 'https://pypi.python.org/pypi/{package}/json'

    def __init__(self, packages):
        self.packages = packages
        self.packages_status_map = {}

    def detect_available_upgrades(self, options):
        prerelease = options['--prerelease']
        explicit_packages_lower = None
        if options['-p'] and options['-p'] != ['all']:
            explicit_packages_lower = [pack_name.lower() for pack_name in options['-p']]

        for i, package in enumerate(self.packages):
            package_name, pinned_version = self._expand_package(package)
            if not package_name or not pinned_version:
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
                if not response.ok:
                    print('pypi API error:', response.reason)
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
                    except KeyError:  # non-RFC versions, get the latest from pypi response
                        latest_version = version.parse(data['info']['version'])
                        latest_version_info = data['releases'][str(latest_version)][0]
                except Exception:
                    print('error while parsing version')
                    continue

                upload_time = latest_version_info['upload_time'].replace('T', ' ')

                # compare versions
                if current_version < latest_version:
                    print('upgrade available: {} ==> {} (uploaded on {})'.format(current_version,
                                                                                 latest_version,
                                                                                 upload_time))
                else:
                    print('up to date: ', current_version)
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

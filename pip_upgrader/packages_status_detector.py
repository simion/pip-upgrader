import os
import re
import sys
from configparser import ConfigParser, NoOptionError, NoSectionError
from urllib.parse import urljoin

import requests
from packaging import version
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from requests import HTTPError

try:
    from pip.locations import site_config_files
except ImportError:
    try:
        from pip._internal.locations import site_config_files
    except ImportError:  # pragma: nocover
        site_config_files = None


class PackagesStatusDetector(object):
    packages = []
    packages_status_map = {}
    PYPI_API_URL = None
    PYPI_API_TYPE = None
    pip_config_locations = [
        '~/.pip/pip.conf',
        '~/.pip/pip.ini',
        '~/.config/pip/pip.conf',
        '~/.config/pip/pip.ini',
    ]

    _prerelease = False

    def __init__(self, packages, options):
        self.packages = packages
        self.packages_status_map = {}
        self.pip_config_locations = list(self.pip_config_locations)
        self.PYPI_API_URL = 'https://pypi.python.org/pypi/{package}/json'
        self.PYPI_API_TYPE = 'pypi_json'

        if not options.get('--use-default-index'):
            self._update_index_url_from_configs()

        self.skip_gte = options.get('--skip-greater-equal', False)
        self._prerelease = False
        timeout_val = options.get('--timeout')
        self._timeout = int(timeout_val) if timeout_val else 15

        # Upgrade constraint: 'patch', 'minor', or None (allow any)
        if options.get('--patch'):
            self._upgrade_constraint = 'patch'
        elif options.get('--minor'):
            self._upgrade_constraint = 'minor'
        else:
            self._upgrade_constraint = None

    def _update_index_url_from_configs(self):
        """Checks for alternative index-url in pip.conf"""

        if 'VIRTUAL_ENV' in os.environ:
            self.pip_config_locations.append(os.path.join(os.environ['VIRTUAL_ENV'], 'pip.conf'))
            self.pip_config_locations.append(os.path.join(os.environ['VIRTUAL_ENV'], 'pip.ini'))

        if site_config_files:
            self.pip_config_locations.extend(site_config_files)

        index_url = None
        custom_config = None

        if 'PIP_INDEX_URL' in os.environ and os.environ['PIP_INDEX_URL']:
            # environ variable takes priority
            index_url = os.environ['PIP_INDEX_URL']
            custom_config = 'PIP_INDEX_URL environment variable'
        else:
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
                    except (NoOptionError, NoSectionError):  # pragma: nocover
                        pass

        if index_url:
            self.PYPI_API_URL = self._prepare_api_url(index_url)
            print(
                'Setting API url to {} as found in {}. Use --use-default-index to use pypi default index'.format(
                    self.PYPI_API_URL, custom_config
                )
            )

    def _prepare_api_url(self, index_url):  # pragma: nocover
        if not index_url.endswith('/'):
            index_url += '/'

        if index_url.endswith('/simple/'):
            self.PYPI_API_TYPE = 'simple_html'
            return urljoin(index_url, '{package}/')

        if index_url.endswith('/+simple/'):
            self.PYPI_API_TYPE = 'simple_html'
            return urljoin(index_url, '{package}/')

        if '/pypi/' in index_url:
            base_url = index_url.split('/pypi/')[0]
            return urljoin(base_url, '/pypi/{package}/json')

        return urljoin(index_url, '/pypi/{package}/json')

    def detect_available_upgrades(self, options):
        self._prerelease = options.get('--prerelease', False)
        explicit_packages_lower = None
        if options['-p'] and options['-p'] != ['all']:
            explicit_packages_lower = [pack_name.lower() for pack_name in options['-p']]

        for i, package in enumerate(self.packages):
            try:
                package_name, pinned_version, pin_type = self._expand_package(package)
                if not package_name or not pinned_version:  # pragma: nocover
                    continue

                if explicit_packages_lower and package_name.lower() not in explicit_packages_lower:
                    found = False
                    package_name_lower = package_name.lower()
                    for option_package in explicit_packages_lower:
                        if re.search(option_package, package_name_lower):
                            found = True
                            break
                    if not found:
                        # skip if explicit and not chosen
                        continue

                current_version = version.parse(pinned_version)

                if pinned_version and isinstance(current_version, version.Version):  # version parsing is correct
                    # Compute max_version constraint for ~= pins
                    max_version = None
                    if pin_type == '~=':
                        max_version = self._compute_compatible_upper_bound(pinned_version)

                    package_status, reason = self._fetch_index_package_info(
                        package_name, current_version, max_version=max_version
                    )
                    if not package_status:  # pragma: nocover
                        print(package, reason)
                        continue

                    print('{}/{}: {} ... '.format(i + 1, len(self.packages), package_name), end='')
                    sys.stdout.flush()

                    # compare versions
                    if current_version < package_status['latest_version']:
                        print(
                            'upgrade available: {} ==> {} (uploaded on {})'.format(
                                current_version, package_status['latest_version'], package_status['upload_time']
                            )
                        )
                    else:
                        print('up to date: {}'.format(current_version))
                    sys.stdout.flush()

                    self.packages_status_map[package_name] = package_status
            except Exception as e:  # noqa  # pragma: nocover
                print('Error while parsing package {} (skipping). \nException: '.format(package), e)

        return self.packages_status_map

    def _fetch_index_package_info(self, package_name, current_version, max_version=None):
        """
        :type package_name: str
        :type current_version: version.Version
        :type max_version: version.Version or None
        """

        try:
            package_canonical_name = canonicalize_name(package_name)
            response = requests.get(self.PYPI_API_URL.format(package=package_canonical_name), timeout=self._timeout)
        except HTTPError as e:  # pragma: nocover
            return False, e.message

        if not response.ok:  # pragma: nocover
            return False, 'API error: {}'.format(response.reason)

        if self.PYPI_API_TYPE == 'pypi_json':
            return self._parse_pypi_json_package_info(package_name, current_version, response, max_version=max_version)
        elif self.PYPI_API_TYPE == 'simple_html':
            return self._parse_simple_html_package_info(
                package_name, current_version, response, max_version=max_version
            )
        else:  # pragma: nocover
            raise NotImplementedError('This type of PYPI_API_TYPE type is not supported')

    def _expand_package(self, package_line):
        pin_types = ['=='] if self.skip_gte else ['==', '>=', '~=']

        for pin_type in pin_types:
            if pin_type in package_line:
                name, vers = package_line.split(pin_type, 1)

                if '[' in name and name.strip().endswith(']'):
                    name = name.split('[')[0]

                # Strip upper bound constraints (e.g. "8.1,<9" -> "8.1")
                if ',' in vers:
                    vers = vers.split(',')[0]

                return name, vers, pin_type

        return None, None, None

    @staticmethod
    def _compute_compatible_upper_bound(version_str):
        """Compute upper bound for ~= compatible release per PEP 440.

        ~=X.Y.Z means >=X.Y.Z, <X.(Y+1).0
        ~=X.Y means >=X.Y, <(X+1).0
        """
        parts = version_str.split('.')
        if len(parts) < 2:
            return None
        # Drop last segment, increment the new last segment
        parts = parts[:-1]
        parts[-1] = str(int(parts[-1]) + 1)
        return version.parse('.'.join(parts))

    def _apply_version_constraints(self, versions, current_version, max_version=None):
        """Filter versions based on upgrade constraint (--minor/--patch) and max_version (~= bound)."""
        if max_version:
            versions = [v for v in versions if v < max_version]
        if self._upgrade_constraint == 'patch':
            versions = [v for v in versions if v.major == current_version.major and v.minor == current_version.minor]
        elif self._upgrade_constraint == 'minor':
            versions = [v for v in versions if v.major == current_version.major]
        return versions

    def _pick_latest_version(self, all_versions, filtered_versions, current_version):
        latest_version = max(filtered_versions)
        if self._prerelease or current_version.is_postrelease or current_version.is_prerelease:
            prerelease_versions = [vers for vers in all_versions if vers.is_prerelease or vers.is_postrelease]
            if prerelease_versions:
                max_prerelease = max(prerelease_versions)
                if max_prerelease > latest_version:
                    latest_version = max_prerelease
        return latest_version

    def _parse_pypi_json_package_info(self, package_name, current_version, response, max_version=None):
        """
        :type package_name: str
        :type current_version: version.Version
        :type response: requests.models.Response
        """

        data = response.json()
        python_version = '{}.{}.{}'.format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
        all_versions = []
        for vers in data['releases'].keys():
            try:
                parsed_ver = version.parse(vers)
            except version.InvalidVersion:
                continue
            # Filter out versions that don't support the current Python
            release_files = data['releases'][vers]

            # Skip yanked versions (all files marked as yanked)
            if release_files and all(f.get('yanked', False) for f in release_files):
                continue

            if release_files:
                requires_python = release_files[0].get('requires_python')
                if requires_python:
                    try:
                        if python_version not in SpecifierSet(requires_python):
                            continue
                    except InvalidSpecifier:
                        pass
            all_versions.append(parsed_ver)
        if not self._prerelease:
            filtered_versions = [vers for vers in all_versions if not vers.is_prerelease and not vers.is_postrelease]
        else:
            filtered_versions = all_versions

        # Apply ~= upper bound and --minor/--patch constraints
        filtered_versions = self._apply_version_constraints(filtered_versions, current_version, max_version)
        all_versions = self._apply_version_constraints(all_versions, current_version, max_version)

        if not filtered_versions:  # pragma: nocover
            return False, 'error while parsing version'

        latest_version = self._pick_latest_version(all_versions, filtered_versions, current_version)
        try:
            try:
                latest_version_info = data['releases'][str(latest_version)][0]
            except KeyError:  # pragma: nocover
                # non-RFC versions, get the latest from pypi response
                latest_version = version.parse(data['info']['version'])
                latest_version_info = data['releases'][str(latest_version)][0]
        except Exception:  # pragma: nocover
            return False, 'error while parsing version'

        upload_time = latest_version_info['upload_time'].replace('T', ' ')

        return {
            'name': package_name,
            'current_version': current_version,
            'latest_version': latest_version,
            'upgrade_available': current_version < latest_version,
            'upload_time': upload_time,
        }, 'success'

    def _parse_simple_html_package_info(self, package_name, current_version, response, max_version=None):
        """
        :type package_name: str
        :type current_version: version.Version
        :type response: requests.models.Response
        """
        normalized_name = re.escape(package_name).replace(r'\-', r'[-_]')
        pattern = r'<a.*>.*{name}-([0-9][A-Za-z0-9\.]*?)(?:-cp|-pp|-py|\.tar).*<\/a>'.format(name=normalized_name)
        versions_match = re.findall(pattern, response.content.decode('utf-8'), flags=re.IGNORECASE)

        all_versions = []
        for vers in versions_match:
            try:
                all_versions.append(version.parse(vers))
            except version.InvalidVersion:
                continue
        filtered_versions = [vers for vers in all_versions if not vers.is_prerelease and not vers.is_postrelease]

        # Apply ~= upper bound and --minor/--patch constraints
        filtered_versions = self._apply_version_constraints(filtered_versions, current_version, max_version)
        all_versions = self._apply_version_constraints(all_versions, current_version, max_version)

        if not filtered_versions:  # pragma: nocover
            return False, 'error while parsing version'

        latest_version = self._pick_latest_version(all_versions, filtered_versions, current_version)

        return {
            'name': package_name,
            'current_version': current_version,
            'latest_version': latest_version,
            'upgrade_available': current_version < latest_version,
            'upload_time': '-',
        }, 'success'

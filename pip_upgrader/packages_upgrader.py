import os

import subprocess
from subprocess import CalledProcessError

import re
from colorclass import Color


class PackagesUpgrader(object):

    selected_packages = None
    requirements_files = None
    upgraded_packages = None
    dry_run = False
    check_gte = False

    def __init__(self, selected_packages, requirements_files, options):
        self.selected_packages = selected_packages
        self.requirements_files = requirements_files
        self.upgraded_packages = []
        self.dry_run = options['--dry-run']
        self.check_gte = options['--check-greater-equal']
        skip_pkg_install = options.get('--skip-package-installation', False)
        if 'PIP_UPGRADER_SKIP_PACKAGE_INSTALLATION' in os.environ:
            skip_pkg_install = True  # pragma: nocover
        self.skip_package_installation = skip_pkg_install

        self.pypi_timeout = 15
        if options['timeout']:
            if options['timeout'].isdecimal():
                self.pypi_timeout = int(options['timeout'])

    def do_upgrade(self):
        for package in self.selected_packages:
            self._update_package(package)

        return self.upgraded_packages

    def _update_package(self, package):
        """ Update (install) the package in current environment,
        and if success, also replace version in file """
        try:
            if not self.dry_run and not self.skip_package_installation:  # pragma: nocover
                pinned = '{}=={}'.format(package['name'],
                                         package['latest_version'])
                subprocess.check_call(['pip', 'install', pinned, '--timeout', self.pypi_timeout])
            else:
                # dry run has priority in messages
                if self.dry_run:
                    lbl = 'Dry Run'
                else:
                    lbl = "Skip Install"  # pragma: nocover
                print('[{}]: skipping package installation:'.format(lbl),
                      package['name'])
            # update only if installation success
            self._update_requirements_package(package)

        except CalledProcessError:  # pragma: nocover
            print(Color('{{autored}}Failed to install package "{}"{{/autored}}'.format(package['name'])))

    def _update_requirements_package(self, package):
        for filename in set(self.requirements_files):
            lines = []

            # read current lines
            with open(filename, 'r') as frh:
                for line in frh:
                    lines.append(line)

            try:
                # write updates lines
                with open(filename, 'w') as fwh:
                    for line in lines:
                        line = self._maybe_update_line_package(line, package)
                        fwh.write(line)
            except Exception as e:  # pragma: nocover
                # at exception, restore old file
                with open(filename, 'w') as fwh:
                    for line in lines:
                        fwh.write(line)
                raise e

    def _maybe_update_line_package(self, line, package):
        original_line = line
        pin_type = r'[>=]=' if self.check_gte else '=='

        pattern = r'\b({package}(?:\[\w*\])?{pin_type})[a-zA-Z0-9\.]+\b'.format(
            package=re.escape(package['name']),
            pin_type=pin_type
        )

        repl = r'\g<1>{}'.format(package['latest_version'])
        line = re.sub(pattern, repl, line)

        if line != original_line:
            self.upgraded_packages.append(package)

            if self.dry_run:  # pragma: nocover
                print('[Dry Run]: skipping requirements replacement:',
                      original_line.replace('\n', ''), ' / ',
                      line.replace('\n', ''))
                return original_line
        return line

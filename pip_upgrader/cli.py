"""
pip-upgrade

Usage:
  pip-upgrade [<requirements_file>] ... [--prerelease] [-p=<package>...] [--skip=<package>...] [--dry-run] [--non-interactive] [--skip-greater-equal] [--use-default-index] [--timeout=<seconds>] [--minor | --patch]

Arguments:
    requirements_file             The requirement FILE, WILDCARD PATH to multiple files, pyproject.toml, or Pipfile.
    --prerelease                  Include prerelease versions for upgrade, when querying pypi repositories.
    -p <package>                  Pre-choose which packages to upgrade. Skips any prompt. You can also use regular expressions to filter packages to upgrade.
    --skip <package>              Skip specific packages (by name or regex). Useful with --non-interactive.
    --dry-run                     Simulates the upgrade, but does not execute the actual upgrade.
    --non-interactive             Upgrade all packages without prompting. Equivalent to -p all.
    --skip-greater-equal          Skip packages with >= and ~= pins (by default ==, >=, and ~= are checked).
    --use-default-index           Skip searching for custom index-url in pip configuration file(s).
    --timeout <seconds>           Set a custom timeout for PyPI requests (default: 15 seconds).
    --minor                       Only upgrade within the same major version (e.g. 1.2.3 -> 1.x.y).
    --patch                       Only upgrade within the same major.minor version (e.g. 1.2.3 -> 1.2.x).

Examples:
  pip-upgrade             # auto discovers requirements file(s), pyproject.toml, and Pipfile
  pip-upgrade requirements.txt
  pip-upgrade pyproject.toml
  pip-upgrade requirements/dev.txt requirements/production.txt
  pip-upgrade requirements.txt -p django -p celery
  pip-upgrade requirements.txt -p all
  pip-upgrade requirements.txt --dry-run  # run everything as a simulation (don't do the actual upgrade)
  pip-upgrade requirements.txt --non-interactive  # upgrade all packages without prompting
  pip-upgrade requirements.txt --non-interactive --skip django --skip celery  # upgrade all except django and celery
  pip-upgrade requirements.txt --minor    # only upgrade within same major version
  pip-upgrade requirements.txt --patch    # only upgrade within same major.minor version

Help:
  Interactively upgrade packages from requirements file, and also update the pinned version from requirements file(s).
  If no requirements are given, the command attempts to detect the requirements file(s) in the current directory.
  Supports ==, >=, and ~= (compatible release) version pins.

  https://github.com/simion/pip-upgrader
"""  # noqa: E501

from docopt import docopt

from pip_upgrader import __version__ as VERSION
from pip_upgrader.packages_detector import PackagesDetector
from pip_upgrader.packages_interactive_selector import PackageInteractiveSelector
from pip_upgrader.packages_status_detector import PackagesStatusDetector
from pip_upgrader.packages_upgrader import PackagesUpgrader
from pip_upgrader.requirements_detector import RequirementsDetector


def get_options():
    return docopt(__doc__, version=VERSION)


def main():
    """Main CLI entrypoint."""
    options = get_options()

    try:
        # 1. detect requirements files
        filenames = RequirementsDetector(options.get('<requirements_file>')).get_filenames()
        if filenames:
            print('Found valid requirements file(s):\n{}'.format('\n'.join(filenames)))
        else:  # pragma: nocover
            print(
                'No requirements files found in current directory. CD into your project '
                'or manually specify requirements files as arguments.'
            )
            return
        # 2. detect all packages inside requirements
        packages = PackagesDetector(filenames).get_packages()

        # 3. query pypi API, see which package has a newer version vs the one in requirements (or current env)
        packages_status_map = PackagesStatusDetector(packages, options).detect_available_upgrades(options)

        # 4. [optionally], show interactive screen when user can choose which packages to upgrade
        if options.get('--non-interactive'):
            if options.get('-p'):
                print('Warning: --non-interactive overrides -p; upgrading all packages.')
            options['-p'] = ['all']
        selected_packages = PackageInteractiveSelector(packages_status_map, options).get_packages()

        # 5. having the list of packages, replace the version inside all filenames
        if not selected_packages:
            return
        upgraded_packages = PackagesUpgrader(selected_packages, filenames, options).do_upgrade()

        pkg_names = ', '.join([package['name'] for package in upgraded_packages])
        if options['--dry-run']:
            print('Dry run complete. Would upgrade: {}'.format(pkg_names))
        else:
            print('\033[32mUpdated versions in requirements for: {}\033[0m'.format(pkg_names))
            print('\033[32mRun `uv sync` or `pip install -r <requirements_file>` to install the new versions.\033[0m')

    except KeyboardInterrupt:  # pragma: nocover
        print('\nUpgrade interrupted.')


if __name__ == '__main__':  # pragma: nocover
    main()

import re
from collections import OrderedDict

import questionary
from questionary import Style

STYLE = Style(
    [
        ('qmark', 'fg:cyan bold'),
        ('question', 'fg:cyan bold'),
        ('pointer', 'fg:cyan bold'),
        ('highlighted', 'fg:cyan'),
        ('selected', 'fg:green'),
        ('instruction', 'fg:yellow'),
    ]
)


class PackageInteractiveSelector(object):
    packages_for_upgrade = OrderedDict()
    selected_packages = []

    def __init__(self, packages_map, options):
        self.selected_packages = []
        self.packages_for_upgrade = {}

        # map with index number, for later choosing
        i = 1
        skip_patterns = [s.lower().strip() for s in (options.get('--skip') or [])]
        skipped_names = []
        for package in packages_map.values():
            if package['upgrade_available']:
                name = package['name'].lower().strip()
                if any(re.fullmatch(pat, name) or re.search(pat, name) for pat in skip_patterns):
                    skipped_names.append(package['name'])
                    continue
                self.packages_for_upgrade[i] = package.copy()
                i += 1

        # maybe all packages are up-to-date
        if not self.packages_for_upgrade:
            skipped_suffix = ' (skipped: {})'.format(', '.join(skipped_names)) if skipped_names else ''
            print('All packages are up-to-date.{}'.format(skipped_suffix))
            return

        # choose which packages to upgrade (interactive or not)
        if skipped_names:
            print('Skipping: {}'.format(', '.join(skipped_names)))
        if '-p' in options and options['-p']:
            if options['-p'] == ['all']:
                self._select_packages(self.packages_for_upgrade.keys())
            else:
                for index, package in self.packages_for_upgrade.items():
                    for chosen_package in options['-p']:
                        if chosen_package.lower().strip() == package['name'].lower().strip():
                            self._select_packages([index])
                        else:
                            if re.search(chosen_package, package['name'].lower().strip()):
                                self._select_packages([index])
        else:
            self.ask_for_packages()

    def get_packages(self):
        return self.selected_packages

    def ask_for_packages(self):
        # Compute column widths from data
        col_num = max(len(str(i)) for i in self.packages_for_upgrade)
        col_name = max(len(p['name']) for p in self.packages_for_upgrade.values())
        col_cur = max(len(str(p['current_version'])) for p in self.packages_for_upgrade.values())
        col_lat = max(len(str(p['latest_version'])) for p in self.packages_for_upgrade.values())
        col_date = max(len(str(p['upload_time'])) for p in self.packages_for_upgrade.values())

        # Ensure minimums for header
        col_num = max(col_num, 1)
        col_name = max(col_name, 7)
        col_cur = max(col_cur, 7)
        col_lat = max(col_lat, 6)
        col_date = max(col_date, 12)

        def fmt_row(num, name, cur, lat, date):
            return f'{num:>{col_num}}  {name:<{col_name}}  {cur:<{col_cur}}  {lat:<{col_lat}}  {date:<{col_date}}'

        header = fmt_row('#', 'Package', 'Current', 'Latest', 'Release date')

        choices = []
        for i, package in self.packages_for_upgrade.items():
            label = fmt_row(
                str(i),
                package['name'],
                str(package['current_version']),
                str(package['latest_version']),
                str(package['upload_time']),
            )
            choices.append(questionary.Choice(label, value=i, checked=False))

        print('')
        selected_values = questionary.checkbox(
            'Select packages to upgrade:\n  ' + header,
            choices=choices,
            style=STYLE,
            instruction='(↑↓ move, space toggle, enter confirm)',
        ).unsafe_ask()

        if not selected_values:
            print('No choice selected.')
            raise KeyboardInterrupt()

        self._select_packages(selected_values)

    def _select_packages(self, indexes):
        selected = []

        for index in indexes:
            if index in self.packages_for_upgrade:
                self.selected_packages.append(self.packages_for_upgrade[index].copy())
                selected.append(True)

        return selected

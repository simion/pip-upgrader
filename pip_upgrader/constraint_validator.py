"""Validate proposed version upgrades against pip's dependency resolver.

When upgrading each package to its latest PyPI version in isolation, the
resulting set of pins can be internally unsatisfiable: one package may cap a
dependency below the "latest" version chosen for another package. This module
runs pip's own resolver (via ``pip install --dry-run --report``) over the
full requirements set (upgraded packages at new versions + all non-upgraded
pins from the original files) and, on conflict, adopts the versions pip
actually resolved to (which are lower but compatible) instead of the latest.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from packaging import version
from packaging.utils import canonicalize_name

# Minimum pip versions for the flags we rely on.
#   --dry-run: pip 21.2
#   --report:  pip 22.2
MIN_PIP_VERSION = version.parse('22.2')


def _get_pip_version():
    """Return the installed pip version as a packaging Version, or None."""
    try:
        import pip

        return version.parse(pip.__version__)
    except Exception:  # pragma: nocover
        return None


def _run_pip_dry_run(requirements_path, report_path):
    """Run pip's resolver in dry-run mode against a requirements file.

    Returns the CompletedProcess. Uses the same interpreter's pip so the
    resolution matches the environment being upgraded.
    """
    cmd = [
        sys.executable,
        '-m',
        'pip',
        'install',
        '--dry-run',
        '--ignore-installed',
        '--report',
        report_path,
        '-r',
        requirements_path,
    ]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def _parse_resolved_versions(report_path):
    """Parse a pip --report JSON file into {canonical_name: Version}."""
    resolved = {}
    with open(report_path) as fh:
        report = json.load(fh)

    for item in report.get('install', []):
        metadata = item.get('metadata', {})
        name = metadata.get('name')
        ver = metadata.get('version')
        if name and ver:
            try:
                resolved[canonicalize_name(name)] = version.parse(ver)
            except version.InvalidVersion:  # pragma: nocover
                continue
    return resolved


def _extract_package_name(line):
    """Return the bare package name from a requirements line, or None."""
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or stripped.startswith('-'):
        return None
    for sep in ('==', '>=', '~=', '<=', '!=', '>', '<'):
        if sep in stripped:
            name = stripped.split(sep)[0].strip()
            if '[' in name:
                name = name.split('[')[0].strip()
            return name or None
    return None


def _find_conflicting_in_output(stdout, selected_packages):
    """Return canonical names of our proposed upgrades mentioned in pip's conflict output."""
    if not stdout:
        return set()
    text = stdout.decode('utf-8', errors='replace') if isinstance(stdout, bytes) else stdout
    text_lower = text.lower()
    upgraded_names = {canonicalize_name(p['name']) for p in selected_packages}
    return {name for name in upgraded_names if name in text_lower}


class ConstraintValidator(object):
    """Adjust selected packages so the resulting pin set is installable."""

    def __init__(self, selected_packages, requirements_filenames=None):
        # selected_packages: list of dicts with 'name' and 'latest_version'
        self.selected_packages = selected_packages
        self.requirements_filenames = requirements_filenames or []

    def validate_and_adjust(self):
        """Validate proposed upgrades; clamp any that pip cannot resolve.

        Mutates and returns ``selected_packages``. Packages whose target
        version pip lowered are updated in place to the resolved version.
        On unrecoverable errors (old pip, resolver failure with no usable
        report) the original selection is returned unchanged with a warning.
        """
        pip_version = _get_pip_version()
        if pip_version is None or pip_version < MIN_PIP_VERSION:
            print(
                'Warning: pip {} is too old for constraint validation '
                '(need >= {}). Skipping --respect-constraints check.'.format(
                    pip_version if pip_version else 'unknown', MIN_PIP_VERSION
                )
            )
            return self.selected_packages

        already_reverted = set()

        # Loop to handle chains of hard conflicts: each iteration either succeeds,
        # handles a soft conflict, or identifies and reverts at least one more package.
        # Terminates in at most len(selected_packages) + 1 iterations.
        while True:
            tmp_dir = tempfile.mkdtemp()
            tmp_reqs = os.path.join(tmp_dir, 'constraint_reqs.txt')
            report_path = os.path.join(tmp_dir, 'report.json')

            upgraded_names = {canonicalize_name(p['name']) for p in self.selected_packages}

            with open(tmp_reqs, 'w') as fh:
                # Write upgraded packages at their proposed new versions.
                for package in self.selected_packages:
                    fh.write('{}=={}\n'.format(package['name'], package['latest_version']))

                # Append non-upgraded lines from original requirements files so
                # pip's resolver sees the full dependency graph, not just the
                # packages being bumped (fixes false-pass when an already-pinned
                # package constrains one of the upgraded packages).
                for filename in self.requirements_filenames:
                    try:
                        with open(filename) as rf:
                            for line in rf:
                                pkg_name = _extract_package_name(line)
                                if pkg_name and canonicalize_name(pkg_name) in upgraded_names:
                                    continue  # already included with new version above
                                fh.write(line)
                    except (IOError, OSError):
                        pass

            try:
                result = _run_pip_dry_run(tmp_reqs, report_path)
            except Exception as exc:  # pragma: nocover
                print('Warning: could not run pip for constraint validation: {}. Skipping.'.format(exc))
                return self.selected_packages

            if result.returncode == 0:
                print('Constraint check passed: all proposed upgrades are compatible with the full requirements set.')
                return self.selected_packages

            if os.path.exists(report_path):
                # Soft conflict: pip resolved to lower-but-compatible versions.
                try:
                    resolved = _parse_resolved_versions(report_path)
                except Exception as exc:  # pragma: nocover
                    print('Warning: could not parse pip report for constraint validation: {}. Skipping.'.format(exc))
                    return self.selected_packages
                self._apply_resolved_versions(resolved)
                return self.selected_packages

            # Hard conflict: pip found no compatible set and produced no report.
            # Try to identify which of our proposed upgrades pip named in the error
            # and revert only those — leaving unrelated upgrades intact.
            conflicting = _find_conflicting_in_output(result.stdout, self.selected_packages)
            new_conflicts = conflicting - already_reverted

            if not new_conflicts:
                # Can't identify any new offending package — fall back to reverting all.
                print(
                    'Warning: pip resolver found a conflict with no compatible set. '
                    'Keeping existing pins for all packages:\n{}'.format(_tail(result.stdout))
                )
                for package in self.selected_packages:
                    package['latest_version'] = package['current_version']
                return self.selected_packages

            for package in self.selected_packages:
                if canonicalize_name(package['name']) in new_conflicts:
                    print(
                        'Constraint conflict: {} held at {} (no compatible upgrade found)'.format(
                            package['name'], package['current_version']
                        )
                    )
                    package['latest_version'] = package['current_version']

            already_reverted |= new_conflicts
            # Continue the loop to re-validate with the remaining pending upgrades.

    def _apply_resolved_versions(self, resolved):
        """Clamp any package whose resolved version is lower than the target."""
        for package in self.selected_packages:
            canonical = canonicalize_name(package['name'])
            if canonical not in resolved:
                continue
            resolved_version = resolved[canonical]
            try:
                target_version = version.parse(str(package['latest_version']))
            except version.InvalidVersion:  # pragma: nocover
                continue
            if resolved_version < target_version:
                print(
                    'Constraint conflict: {} {} -> {} (capped by other packages)'.format(
                        package['name'], target_version, resolved_version
                    )
                )
                package['latest_version'] = str(resolved_version)


def _tail(output, max_lines=15):
    """Return the last few lines of captured subprocess output for logging."""
    if not output:
        return ''
    if isinstance(output, bytes):
        output = output.decode('utf-8', errors='replace')
    lines = re.split(r'\r?\n', output.strip())
    return '\n'.join(lines[-max_lines:])

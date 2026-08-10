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


def _iter_requirements_lines(filenames, skip_packages, _visited=None):
    """Yield non-package lines from requirements files, recursively resolving -r includes.

    Lines defining a package in ``skip_packages`` (canonical names) are dropped so
    the caller can prepend its own proposed versions without creating duplicate pins.
    ``-r`` includes are inlined rather than forwarded as-is so the temp file has no
    relative-path references that would break when it lives in a different directory.
    ``-c`` constraint file paths are rewritten to absolute so they resolve correctly.
    """
    if _visited is None:
        _visited = set()

    for filename in filenames:
        abs_path = os.path.abspath(filename)
        if abs_path in _visited:
            continue
        _visited.add(abs_path)
        source_dir = os.path.dirname(abs_path)

        try:
            with open(abs_path) as fh:
                for line in fh:
                    stripped = line.strip()

                    # Recursively inline -r / --requirement includes.
                    for flag in ('-r ', '--requirement '):
                        if stripped.startswith(flag):
                            inc = stripped[len(flag) :].strip()
                            if not os.path.isabs(inc):
                                inc = os.path.join(source_dir, inc)
                            yield from _iter_requirements_lines([inc], skip_packages, _visited)
                            break
                    else:
                        # Rewrite -c / --constraint paths to absolute.
                        for flag in ('-c ', '--constraint '):
                            if stripped.startswith(flag):
                                inc = stripped[len(flag) :].strip()
                                if not os.path.isabs(inc):
                                    line = flag + os.path.join(source_dir, inc) + '\n'
                                break

                        pkg_name = _extract_package_name(line)
                        if pkg_name and canonicalize_name(pkg_name) in skip_packages:
                            continue  # caller will write this at the proposed new version
                        yield line
        except (IOError, OSError):
            pass


def _find_conflicting_in_output(stdout, selected_packages):
    """Return canonical names of our proposed upgrades that pip identifies as the conflict root.

    pip>=22 emits "The user requested X==Y" in the conflict block for each package we pinned
    that is part of the conflict. We parse those lines first so innocent packages that merely
    appear in "Collecting X" download lines are not wrongly blamed.

    Falls back to a broad name search only when pip's output has no "The user requested" lines
    (older pip format or a very different error message).
    """
    if not stdout:
        return set()
    text = stdout.decode('utf-8', errors='replace') if isinstance(stdout, bytes) else stdout
    upgraded_names = {canonicalize_name(p['name']) for p in selected_packages}

    user_requested = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith('the user requested '):
            rest = stripped[len('the user requested ') :]
            m = re.match(r'([A-Za-z0-9._-]+)', rest)
            if m:
                canonical = canonicalize_name(m.group(1))
                if canonical in upgraded_names:
                    user_requested.add(canonical)

    if user_requested:
        return user_requested

    # Fallback: broad search. May over-match ("Collecting X" lines name innocent packages).
    text_lower = text.lower()
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

                # Inline all requirements (recursively resolving -r includes,
                # rewriting -c constraint paths to absolute) so the temp file
                # has no relative-path references that break when placed in a
                # different directory. Upgraded packages are filtered out here
                # since they were already written above with their new version.
                for line in _iter_requirements_lines(self.requirements_filenames, upgraded_names):
                    fh.write(line)

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

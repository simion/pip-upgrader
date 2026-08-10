"""Find CVE-vulnerable packages and their minimum safe fix version via pip-audit.

Used by ``--cve-only`` to restrict upgrades to packages with known
vulnerabilities, pinning each to the lowest version that clears every CVE
affecting it (rather than the latest PyPI release).
"""

import json
import os
import subprocess

from packaging import version
from packaging.utils import canonicalize_name

# pip-audit is not importable as a library here; it's invoked as a CLI. Prefer
# the user-local install location, falling back to whatever is on PATH.
PIP_AUDIT_CANDIDATES = [
    os.path.expanduser('~/.local/bin/pip-audit'),
    'pip-audit',
]


def _find_pip_audit():
    for candidate in PIP_AUDIT_CANDIDATES:
        if os.path.sep in candidate:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        else:
            return candidate
    return None  # pragma: nocover


def _min_safe_version(vulns):
    """Return the lowest version that clears every vuln, or None.

    Each vuln lists the versions that fix it. A version is safe only once it
    is at or above the minimum fix of *every* vuln, so the answer is the
    maximum across each vuln's own minimum fix version.
    """
    per_vuln_minimums = []
    for vuln in vulns:
        fix_versions = vuln.get('fix_versions') or []
        parsed = []
        for fix in fix_versions:
            try:
                parsed.append(version.parse(fix))
            except version.InvalidVersion:  # pragma: nocover
                continue
        if not parsed:
            # A vuln with no known fix can't be resolved by upgrading.
            return None
        per_vuln_minimums.append(min(parsed))

    if not per_vuln_minimums:
        return None
    return max(per_vuln_minimums)


class CVEAuditor(object):
    """Run pip-audit over requirements files and report minimum safe fixes."""

    def __init__(self, filenames):
        self.filenames = filenames

    def get_min_fix_versions(self):
        """Return ``{canonical_name: min_fix_version_str}`` for fixable CVEs.

        Packages with vulnerabilities but no available fix are skipped with a
        warning. If pip-audit is missing or fails, an empty dict is returned so
        the caller degrades gracefully.
        """
        pip_audit = _find_pip_audit()
        if not pip_audit:  # pragma: nocover
            print('Warning: pip-audit not found. Skipping --cve-only filtering.')
            return {}

        result = {}
        for filename in self.filenames:
            dependencies = self._run_pip_audit(pip_audit, filename)
            if dependencies is None:
                continue
            for dep in dependencies:
                name = dep.get('name')
                vulns = dep.get('vulns') or []
                if not name or not vulns:
                    continue

                min_fix = _min_safe_version(vulns)
                if min_fix is None:
                    print('Warning: {} is vulnerable but has no fix version available. Skipping.'.format(name))
                    continue

                canonical = canonicalize_name(name)
                # Multiple files may list the same package; keep the highest
                # required fix so every file's CVEs are covered.
                existing = result.get(canonical)
                if existing is None or version.parse(min_fix) > version.parse(existing):
                    result[canonical] = str(min_fix)

        return result

    def _run_pip_audit(self, pip_audit, filename):
        """Run pip-audit on a single file; return its dependency list or None."""
        cmd = [
            pip_audit,
            '-r',
            filename,
            '-f',
            'json',
            '--no-deps',
            '--cache-dir',
            '/tmp/pip-audit-cache',
        ]
        env = dict(os.environ)
        env.setdefault('REQUESTS_CA_BUNDLE', '/tmp/onecli-combined-ca.pem')

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        except Exception as exc:  # pragma: nocover
            print('Warning: could not run pip-audit on {}: {}. Skipping.'.format(filename, exc))
            return None

        if not proc.stdout:  # pragma: nocover
            print('Warning: pip-audit produced no output for {}. Skipping.'.format(filename))
            return None

        try:
            report = json.loads(proc.stdout.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as exc:  # pragma: nocover
            print('Warning: could not parse pip-audit output for {}: {}. Skipping.'.format(filename, exc))
            return None

        return report.get('dependencies', [])

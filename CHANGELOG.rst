2.4.12 (2026-08-10)
---------------------
* fix ``--respect-constraints`` with multi-file requirements using ``-r`` includes (#83)
* relative ``-r`` paths (e.g. ``-r base.txt``) could not be resolved when the temp file was written to an isolated temp directory, causing pip to error with "Could not open requirements file" and fall back to reverting all packages
* ``-r`` includes are now recursively inlined into the temp file; ``-c`` constraint paths are rewritten to absolute so they also resolve correctly

2.4.11 (2026-08-10)
---------------------
* fix ``--respect-constraints`` surgical hard-conflict handling: when pip names specific packages in the conflict error, only those packages are reverted to their current pin — unrelated upgrades in the same run now proceed normally (#83)
* the fallback (revert all) still applies when the conflict output cannot be parsed to identify the offending package

2.4.10 (2026-08-10)
---------------------
* fix ``--respect-constraints`` hard-conflict case: when pip can find no compatible set and produces no report, packages are now reverted to their current pins instead of writing the unsatisfiable upgrade (#83)

2.4.9 (2026-08-10)
---------------------
* fix ``--respect-constraints`` false-pass when a non-upgraded package constrains one of the bumped packages (#83)
* the resolver now sees the full requirements set (all existing pins + proposed new versions) rather than only the upgraded packages, so cross-package caps like ``django-celery-beat<6.1`` are caught and honoured

2.4.8 (2026-08-10)
---------------------
* add ``--cve-only`` flag that runs pip-audit and upgrades only packages with known CVEs, each to the minimum version that clears every vulnerability affecting it (rather than the latest PyPI release) (#65)
* the minimum safe version is the max across each vulnerability's own minimum fix version, so the resulting pin is free of all reported CVEs
* vulnerable packages with no available fix are skipped with a warning; if pip-audit is missing the flag degrades gracefully and skips CVE filtering
* composes with ``--non-interactive``, ``--dry-run`` and ``--respect-constraints``

2.4.7 (2026-08-10)
---------------------
* add ``--min-age-days=<N>`` flag that skips candidate versions published less than N days ago, providing a cooldown period that protects against malicious packages that appear briefly on PyPI (#66)
* the cutoff is taken from the latest ``upload_time`` across all distribution files of a candidate version; when a version has no upload time metadata it is kept (fail open)

2.4.6 (2026-08-10)
---------------------
* add ``--respect-constraints`` flag that validates proposed upgrades against pip's resolver and clamps any that would produce unsatisfiable pins to the highest compatible version (#83)
* constraint validation runs by default with ``--non-interactive``; disable it with ``--no-respect-constraints``
* validation is skipped with a warning when pip is older than 22.2 (``--report`` support)

1.4.0 (2017-05-12)
---------------------
* support for custom index-url, scanned from several sources (pip configs, PIP_INDEX_URL environment variable)
* option to disable detection of custom index url, and use default pypi index
* virtualenv detection + warning if you're about to install packages in system's python interpreter. Can be bypassed with `--skip-virtualenv-check` or `--skip-package-installation`
* support for parsing plain html indexes (tested with devpi and Artifactory)

1.3.5 (initial release + many improvements from your feedback)
---------------------

* initial release, and right after, man improvements based on your feedback

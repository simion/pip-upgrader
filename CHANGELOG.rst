1.4.0 (2017-05-12)
---------------------
* support for custom index-url, scanned from several sources (pip configs, PIP_INDEX_URL environment variable)
* option to disable detection of custom index url, and use default pypi index
* virtualenv detection + warning if you're about to install packages in system's python interpreter. Can be bypassed with `--skip-virtualenv-check` or `--skip-package-installation`
* support for parsing plain html indexes (tested with devpi and Artifactory)

1.3.5 (initial release + many improvements from your feedback)
---------------------

* initial release, and right after, man improvements based on your feedback

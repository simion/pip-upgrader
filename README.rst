pip-upgrader
=========
.. image:: https://travis-ci.org/simion/pip-upgrader.svg?branch=master
    :target: https://travis-ci.org/simion/pip-upgrader
.. image:: https://coveralls.io/repos/github/simion/pip-upgrader/badge.svg?branch=master
    :target: https://coveralls.io/github/simion/pip-upgrader?branch=master


An interactive pip requirements upgrader. Because upgrading requirements, package by package, is a pain in the ass.
It also updates the version in your requirements.txt file.


Purpose
-------

This cli tools helps you interactively(or not) upgrade packages from requirements file,
and also **update the pinned version from requirements file(s)**.

If no requirements are given, the command **attempts to detect the requirements file(s)** in the current directory.

Quick preview:

.. image:: https://raw.githubusercontent.com/simion/pip-upgrader/master/demo.gif

Installation
------------

::

    pip install pip-upgrader

Usage
-----
**Activate your virtualenv** (important, because it will also install the new versions of upgraded packages in current virtualenv)

**CD into your project.**
Then:
::

    $ pip-upgrade

Arguments:
::

    requirements_file(s)          The requirement FILE, or WILDCARD PATH to multiple files. (positional arguments)
    --prerelease                  Include prerelease versions for upgrade, when querying pypi repositories.
    -p <package>                  Pre-choose which packages tp upgrade. Skips any prompt.
    --dry-run                     Simulates the upgrade, but does not execute the actual upgrade.
    --skip-package-installation   Only upgrade the version in requirements files, don't install the new package.
    --skip-virtualenv-check       Disable virtualenv check. Allows installing the new packages outside the virtualenv.
    --use-default-index           Skip searching for custom index-url in pip configuration file(s).

Examples:

::

    pip-upgrade             # auto discovers requirements file. Prompts for selecting upgrades
    pip-upgrade requirements.txt
    pip-upgrade requirements/dev.txt requirements/production.txt

    # skip prompt and manually choose some/all packages for upgrade
    pip-upgrade requirements.txt -p django -p celery
    pip-upgrade requirements.txt -p all

    # include pre-release versions
    pip-upgrade --prerelease


Features
--------

to be completed

Final notes
-----------
If you encounter any bugs, please open an issue and it will be magically resolved :)

**TODO:**

- implement some sort of dependency detection, and nested display. Useful for requirements generated with pip freeze.
- support for :code:`package>=0.1.0` (only works for :code:`package==0.1.0`)


Have fun! :)

Contributing
------------
Clone the repository, create a virtualenv, then run:
::

    pip install -e .[test]
    py.test

This command will :

- run tests
- print coverage report
- print pep8 errors

For detailed coverage report, after *py.test* run
::

    coverage html && open htmlcov/index.html

**Testing against all python version**
Make sure you have python 2.7, 3.5, 3.6 installed (maybe use pyenv). Then: 
::

    pip install tox

    tox

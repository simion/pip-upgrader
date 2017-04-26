pip-upgrader
=========

*An interactive pip requirements upgrader. Because upgrading requirements, package by package, is a pain in the ass.
It also updates the version in your requirements.txt file.


Purpose
-------

This cli tools helps you interactively(or not) upgrade packages from requirements file,
and also **update the pinned version from requirements file(s)**.

If no requirements are given, the command **attempts to detect the requirements file(s)** in the current directory.

Installation
------------

::

    pip install pip-upgrader

Usage
-----
Activate your virtualenv.
CD into your project.
Then:
::

    $ pip-upgrade [<requirements_file>] ... [--prerelease] [-p=<package>...]

Arguments:
    requirements_file       The requirement FILE, or WILDCARD PATH to multiple files.
    --prerelease            Include prerelease versions for upgrade, when querying pypi repositories.
    -p <package>            Pre-choose which packages tp upgrade. Skips any prompt.


Examples:

::

    pip-upgrade             # auto discovers requirements file
    pip-upgrade requirements.txt
    pip-upgrade requirements/dev.txt requirements/production.txt
    pip-upgrade requirements.txt -p django -p celery
    pip-upgrade requirements.txt -p all


Have fun! :)

::
Note for me:
Release new version:
::

    $ python setup.py sdist bdist_wheel
    $ twine upload dist/* -u my_username -p my_pass

# pip-upgrader [![Build Status](https://travis-ci.org/simion/pip-upgrader.svg?branch=master)](https://travis-ci.org/simion/pip-upgrader)

An interactive pip requirements upgrader. Because upgrading
requirements, package by package, is a pain in the ass. It also updates
the version in your requirements.txt file.

## Purpose

This cli tools helps you interactively(or not) upgrade packages from
requirements file, and also **update the pinned version from
requirements file(s)**.

If no requirements are given, the command **attempts to detect the
requirements file(s)** in the current directory.

Quick preview:

![image](https://raw.githubusercontent.com/simion/pip-upgrader/master/demo.gif)

## Installation

    pip install pip-upgrader

**Note:** this packages installs the following requirements: `'docopt',
'packaging', 'requests', 'terminaltables', 'colorclass'`

To avoid installing all these dependencies in your project, you can
install `pip-upgrader` in your system, rather than your virtualenv. If
you install it in your system, and need to upgrade it, run `pip install
-U pip-upgrader`

## Usage

**Activate your virtualenv** (important, because it will also install
the new versions of upgraded packages in current virtualenv)

**CD into your project.** Then: :

    $ pip-upgrade

Arguments: :

    requirements_file(s)          The requirement FILE, or WILDCARD PATH to multiple files. (positional arguments)
    --prerelease                  Include prerelease versions for upgrade, when querying pypi repositories.
    -p <package>                  Pre-choose which packages tp upgrade. Skips any prompt.
    --dry-run                     Simulates the upgrade, but does not execute the actual upgrade.
    --skip-package-installation   Only upgrade the version in requirements files, don't install the new package.
    --skip-virtualenv-check       Disable virtualenv check. Allows installing the new packages outside the virtualenv.
    --use-default-index           Skip searching for custom index-url in pip configuration file(s).

Examples:

    pip-upgrade             # auto discovers requirements file. Prompts for selecting upgrades
    pip-upgrade requirements.txt
    pip-upgrade requirements/dev.txt requirements/production.txt

    # skip prompt and manually choose some/all packages for upgrade
    pip-upgrade requirements.txt -p django -p celery
    pip-upgrade requirements.txt -p all

    # include pre-release versions
    pip-upgrade --prerelease

To use `pip-upgrader` on install requirements located in a `setup.py`
file, try this:

``` sh
./setup.py egg_info
pip-upgrade $(./setup.py --name | tr -- - _)*.egg-info/requires.txt
```

This will display any versions that can be upgraded, and helps you to
manually main

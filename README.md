# pip-upgrader [![Build Status](https://travis-ci.org/simion/pip-upgrader.svg?branch=master)](https://travis-ci.org/simion/pip-upgrader)

An interactive pip requirements upgrader. Because upgrading requirements, package by package, is a pain in the ass. It also updates the version in your requirements.txt file.

**Note**: Currently unmaintained. I'm using [poetry](https://python-poetry.org/) for all my projects, but I'm happy to review and release PRs.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Specifying Requirements Files](#specifying-requirements-files)
  - [Skipping the Interactive Prompt](#skipping-the-interactive-prompt)
  - [Including Prerelease Versions](#including-prerelease-versions)
  - [Dry Run Mode](#dry-run-mode)
  - [Skipping Package Installation](#skipping-package-installation)
  - [Skipping Virtual Environment Check](#skipping-virtual-environment-check)
  - [Using Default Index URL](#using-default-index-url)
  - [Using pip-upgrader with setup.py](#using-pip-upgrader-with-setuppy)
- [Examples](#examples)
  - [Auto-Discovery of Requirements Files](#auto-discovery-of-requirements-files)
  - [Upgrading Specific Packages](#upgrading-specific-packages)
  - [Upgrading All Packages Without Prompting](#upgrading-all-packages-without-prompting)
  - [Including Prerelease Versions](#including-prerelease-versions-example)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

## Overview

`pip-upgrader` is a command-line utility designed to ease the process of upgrading Python packages in your project. It allows for both interactive and non-interactive upgrading of packages listed in your requirements files and automatically updates the pinned versions in those files. 

This tool helps automate the often tedious task of upgrading packages, ensuring your project dependencies are up to date with minimal effort. The interactive mode prompts you to upgrade each package individually, while the non-interactive mode can batch upgrade all selected packages.

Quick preview:

![image](https://raw.githubusercontent.com/simion/pip-upgrader/master/demo.gif)

### Key Features

- **Interactive Mode**: Upgrade packages with a prompt that allows you to select which packages to upgrade.
- **Automatic Requirements Update**: Automatically updates the version numbers in your `requirements.txt` or other specified requirements files.
- **Batch Upgrading**: Allows upgrading of all or specific packages in a batch mode.
- **Dry Run Mode**: Provides a simulation of the upgrade process without making any actual changes.
- **Prerelease Support**: Allows inclusion of prerelease versions when upgrading packages.
- **Multiple Requirements Files**: Supports upgrading from multiple requirements files simultaneously.

## Installation

To install `pip-upgrader`, use the following command:

```bash
pip install pip-upgrader
```

**Note**: Installing `pip-upgrader` will also install the following dependencies:
- `docopt`
- `packaging`
- `requests`
- `terminaltables`
- `colorclass`

If you wish to avoid installing these dependencies in your project's virtual environment, consider installing `pip-upgrader` globally on your system. To upgrade `pip-upgrader`, run:

```bash
pip install -U pip-upgrader
```

## Usage

### Basic Usage

To begin using `pip-upgrader`, activate your virtual environment and navigate to your project directory. Then run:

```bash
pip-upgrade
```

This command will automatically detect any requirements files in your current directory and prompt you to select which packages you would like to upgrade.

### Specifying Requirements Files

If you need to upgrade packages listed in specific requirements files, you can specify these files as positional arguments:

```bash
pip-upgrade requirements.txt
pip-upgrade requirements/dev.txt requirements/production.txt
```

### Skipping the Interactive Prompt

If you already know which packages you want to upgrade, you can skip the interactive prompt by specifying the packages with the `-p` option:

```bash
pip-upgrade requirements.txt -p django -p celery
```

To upgrade all packages without any prompts, use:

```bash
pip-upgrade requirements.txt -p all
```

### Including Prerelease Versions

To include prerelease versions when upgrading your packages, use the `--prerelease` option:

```bash
pip-upgrade --prerelease
```

This option is particularly useful if you want to test your project with the latest prerelease versions of your dependencies.

### Dry Run Mode

To simulate the upgrade process without making any actual changes to your environment or requirements files, use the `--dry-run` option:

```bash
pip-upgrade --dry-run
```

This allows you to review which packages would be upgraded without committing to any changes.

### Skipping Package Installation

If you want to update the versions in your requirements files without actually installing the new versions of the packages, use the `--skip-package-installation` option:

```bash
pip-upgrade --skip-package-installation
```

This is useful if you want to update your requirements files first and install the packages later.

### Skipping Virtual Environment Check

By default, `pip-upgrader` checks whether you're working inside a virtual environment to prevent installing packages globally by mistake. To disable this check and allow installation outside of a virtual environment, use the `--skip-virtualenv-check` option:

```bash
pip-upgrade --skip-virtualenv-check
```

### Using Default Index URL

If you want to skip searching for a custom index URL in pip configuration files and use the default PyPI index, use the `--use-default-index` option:

```bash
pip-upgrade --use-default-index
```

### Using pip-upgrader with setup.py

To upgrade packages listed in a `setup.py` file, you can use the following commands:

```bash
./setup.py egg_info
pip-upgrade $(./setup.py --name | tr -- - _)*.egg-info/requires.txt
```

This approach will display any versions that can be upgraded, helping you to manually maintain the dependencies specified in `setup.py`.

## Examples

### Auto-Discovery of Requirements Files

Running `pip-upgrade` without any arguments will automatically detect requirements files in the current directory and prompt you for upgrades:

```bash
pip-upgrade
```

### Upgrading Specific Packages

To upgrade only selected packages, specify the packages with the `-p` option:

```bash
pip-upgrade requirements.txt -p django -p celery
```

### Upgrading All Packages Without Prompting

To upgrade all packages listed in your requirements files without any interactive prompts:

```bash
pip-upgrade requirements.txt -p all
```

### Including Prerelease Versions Example

To include prerelease versions of packages during the upgrade process:

```bash
pip-upgrade --prerelease
```

This is useful if you want to work with the latest prerelease versions available on PyPI.

## FAQ

**Q: Can I use `pip-upgrader` in projects without a requirements file?**

A: Yes, `pip-upgrader` attempts to detect `requirements.txt` or similar files in your current directory. If no files are found, it will not perform any upgrades.

**Q: What happens if I run `pip-upgrader` outside of a virtual environment?**

A: By default, `pip-upgrader` checks whether you're inside a virtual environment to avoid global package installations. However, you can bypass this check using the `--skip-virtualenv-check` option.

**Q: How do I know which packages are safe to upgrade?**

A: `pip-upgrader` will prompt you to confirm each upgrade, allowing you to skip packages that you may want to upgrade later or that have breaking changes.

## Contributing

We welcome contributions to the `pip-upgrader` project! Here's how you can contribute:

1. **Fork the Repository**: Start by forking the `pip-upgrader` repository on GitHub.

2. **Create a New Branch**: Create a new branch for your feature or bug fix:

   ```bash
   git checkout -b your-feature-branch
   ```

3. **Make Your Changes**: Implement your changes, whether it's adding new features, fixing bugs, or enhancing documentation.

4. **Commit and Push**: Commit your changes with a clear commit message:

   ```bash
   git commit -m "Add detailed documentation for pip-upgrader"
   git push origin your-feature-branch
   ```

5. **Create a Pull Request**: Navigate to your fork on GitHub and submit a pull request to the main repository. Be sure to reference any related issues in your PR description.

6. **Engage in the Review Process**: Be prepared to make changes and respond to feedback from the repository maintainers.

## License

`pip-upgrader` is open-source software licensed under the Apache License Version 2.0. See the [LICENSE](LICENSE) file for more details.
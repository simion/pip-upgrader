"""Packaging settings."""


from codecs import open
from os.path import abspath, dirname, join
from subprocess import call

from setuptools import Command, find_packages, setup


this_dir = abspath(dirname(__file__))
with open(join(this_dir, 'README.rst'), encoding='utf-8') as file:
    long_description = file.read()


class RunTests(Command):
    """ Run all tests. """
    description = 'run tests'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """Run all tests!"""
        err = call(['py.test'])
        raise SystemExit(err)


setup(
    name='pip_upgrader',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    description='An interactive pip requirements upgrader. It also updates the version in your requirements.txt file.',
    long_description=long_description,
    url='https://github.com/simion/pip-upgrader',
    author='Simion Baws',
    author_email='simion.agv@gmail.com',
    license='Apache License 2.0',
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Utilities',
        'License :: Public Domain',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='cli,pip,pypi,requirements,upgrade',
    packages=find_packages(exclude=['docs', 'tests*']),
    install_requires=['docopt', 'packaging', 'requests', 'terminaltables', 'colorclass'],
    extras_require={
        'test': ['coverage', 'pytest', 'pytest-cov', 'pytest-pep8', 'mock', 'responses'],
    },
    entry_points={
        'console_scripts': [
            'pip-upgrade=pip_upgrader.cli:main',
        ],
    },
    cmdclass={'test': RunTests},
)

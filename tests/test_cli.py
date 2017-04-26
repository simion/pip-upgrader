"""Tests for our main skele CLI module."""


from subprocess import PIPE, Popen as popen
from unittest import TestCase

from pip_upgrader import __version__ as VERSION


class TestHelp(TestCase):
    def test_returns_usage_information(self):
        output = popen(['pip-upgrade', '-h'], stdout=PIPE).communicate()[0]
        self.assertTrue('Usage:' in output)

        output = popen(['pip-upgrade', '--help'], stdout=PIPE).communicate()[0]
        self.assertTrue('Usage:' in output)


class TestVersion(TestCase):
    def test_returns_version_information(self):
        output = popen(['pip-upgrade', '--version'], stdout=PIPE).communicate()[0]
        self.assertEqual(output.strip(), VERSION)


# class TestCommand(TestCase):
#     # todo: implement the actual tests
#
#     def test_command_auto_discovery(self):
#         output = popen(['pip-upgrade'], stdout=PIPE).communicate()[0]
#         print(output)
#
#     def test_command_single_file(self):
#         output = popen(['pip-upgrade', 'requirements.txt'], stdout=PIPE).communicate()[0]
#         print(output)
#
#     def test_command_multiple_files(self):
#         output = popen(['pip-upgrade', 'requirements/*.txt'], stdout=PIPE).communicate()[0]
#         print(output)

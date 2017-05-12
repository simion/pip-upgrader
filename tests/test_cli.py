from __future__ import unicode_literals

from subprocess import PIPE, Popen as popen
from unittest import TestCase

import responses
from packaging.utils import canonicalize_name

from pip_upgrader import __version__ as VERSION

from pip_upgrader import cli
from pip_upgrader.packages_status_detector import PackagesStatusDetector

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

try:
    from io import StringIO
except ImportError:  # pragma: nocover
    from cStringIO import StringIO


class TestHelp(TestCase):
    def test_returns_usage_information(self):
        output = popen(['pip-upgrade', '-h'], stdout=PIPE).communicate()[0]
        self.assertTrue('Usage:' in output.decode('utf-8'))

        output = popen(['pip-upgrade', '--help'], stdout=PIPE).communicate()[0]
        self.assertTrue('Usage:' in output.decode('utf-8'))


class TestVersion(TestCase):
    def test_returns_version_information(self):
        output = popen(['pip-upgrade', '--version'], stdout=PIPE).communicate()[0]
        self.assertEqual(output.strip().decode('utf-8'), VERSION)


@patch('pip_upgrader.packages_interactive_selector.user_input', return_value='all')
@patch('pip_upgrader.virtualenv_checker.is_virtualenv', return_value=True)
class TestCommand(TestCase):

    def _add_responses_mocks(self):
        for package in ['Django', 'celery', 'django-rest-auth', 'ipython']:
            with open('tests/fixtures/{}.json'.format(package)) as fh:
                body = fh.read()

            responses.add(responses.GET,
                          "https://pypi.python.org/pypi/{}/json".format(package),
                          body=body,
                          content_type="application/json")

            with open('tests/fixtures/{}.html'.format(canonicalize_name(package))) as fh:
                body_html = fh.read()
            responses.add(responses.GET,
                          "https://pypi.python.org/simple/{}".format(canonicalize_name(package)),
                          body=body_html)

    def setUp(self):
        self._add_responses_mocks()

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': []})
    def test_command_basic_usage(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(user_input_mock.called)

        self.assertIn('Available upgrades', output)
        self.assertIn('ipython ... up to date', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('Successfully upgraded', output)
        self.assertIn('this was a simulation using --dry-run', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': []})
    def test_command_simple_html_index_url(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock, \
                patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations',
                      new=PackagesStatusDetector.pip_config_locations + ['pip.test.conf']):
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(user_input_mock.called)
        # checks if new index-url was discovered from config file
        self.assertIn('Setting API url', output)
        self.assertIn('https://pypi.python.org/simple/{package}', output)

        self.assertIn('Available upgrades', output)
        self.assertIn('ipython ... up to date', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('Successfully upgraded', output)
        self.assertIn('this was a simulation using --dry-run', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': []})
    @patch.dict('os.environ', {'PIP_INDEX_URL': 'https://pypi.python.org/simple/'})
    def test_command_pip_index_url_environ(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(user_input_mock.called)
        # checks if new index-url was discovered from config file
        self.assertIn('Setting API url', output)
        self.assertIn('https://pypi.python.org/simple/{package}', output)

        self.assertIn('Available upgrades', output)
        self.assertIn('ipython ... up to date', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('Successfully upgraded', output)
        self.assertIn('this was a simulation using --dry-run', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': [], '--use-default-index': True})
    def test_command__use_default_index(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock, \
                patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations',
                      new=PackagesStatusDetector.pip_config_locations + ['pip.test.conf']):
            cli.main()
            output = stdout_mock.getvalue()

        # checks if new index-url was discovered from config file
        self.assertNotIn('Setting API url', output)
        self.assertIn('Successfully upgraded', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': []})
    def test_command_interactive_bad_choices(self, options_mock, is_virtualenv_mock, user_input_mock):

        user_input_mock.return_value = ''
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(user_input_mock.called)
        self.assertIn('No choice selected', output)
        self.assertNotIn('Setting API url', output)

        user_input_mock.return_value = '5 6 7'
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(user_input_mock.called)
        self.assertIn('No valid choice selected.', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': ['all']})
    def test_command_not_interactive_all_packages(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # no user_input should be called
        self.assertFalse(user_input_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertNotIn('Available upgrades', output)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertIn('ipython ... up to date', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)

        self.assertIn('Successfully upgraded', output)
        self.assertIn('this was a simulation using --dry-run', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': ['django', 'bad_package']})
    def test_command_not_interactive_specific_package(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # no user_input should be called
        self.assertFalse(user_input_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipython ... up to date', output)
        self.assertNotIn('ipdb', output)
        self.assertNotIn('celery ... upgrade available: 3.1.1 ==>', output)

        self.assertIn('Successfully upgraded', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': ['ipython']})
    def test_command_not_interactive_all_packages_up_to_date(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # no user_input should be called
        self.assertFalse(user_input_mock.called)
        self.assertNotIn('Setting API url', output)
        self.assertIn('All packages are up-to-date.', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': ['all'],
                                                         '<requirements_file>': ['requirements/production.txt']})
    def test_command_not_interactive_explicit_requirements(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # no user_input should be called
        self.assertFalse(user_input_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertNotIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipython ... up to date', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)

        self.assertIn('Successfully upgraded', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': ['django'], '--prerelease': True})
    def test_command_not_specific_package_prerelease(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # no user_input should be called
        self.assertFalse(user_input_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==> 1.11rc1', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipython ... up to date', output)
        self.assertNotIn('ipdb', output)
        self.assertNotIn('celery ... upgrade available: 3.1.1 ==>', output)

        self.assertIn('Successfully upgraded', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '-p': ['django'], '--prerelease': True})
    def test_command_not_specific_package_prerelease_html_api(self, options_mock, is_virtualenv_mock, user_input_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock, \
                patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations',
                      new=PackagesStatusDetector.pip_config_locations + ['pip.test.conf']):
            cli.main()
            output = stdout_mock.getvalue()

        # no user_input should be called
        self.assertFalse(user_input_mock.called)

        self.assertIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==> 1.11rc1', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipython ... up to date', output)
        self.assertNotIn('ipdb', output)
        self.assertNotIn('celery ... upgrade available: 3.1.1 ==>', output)

        self.assertIn('Successfully upgraded', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '--skip-virtualenv-check': False,
                                                         '-p': ['django']})
    def test_command_not_interactive_not_virtualenv(self, options_mock, is_virtualenv_mock, user_input_mock):
        is_virtualenv_mock.return_value = False

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertNotIn('Setting API url', output)
        self.assertIn("It seems you haven't activated a virtualenv", output)
        self.assertNotIn('Successfully upgraded', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value={'--dry-run': True, '--skip-virtualenv-check': True,
                                                         '-p': ['django']})
    def test_command_not_interactive_not_virtualenv_skip(self, options_mock, is_virtualenv_mock, user_input_mock):
        is_virtualenv_mock.return_value = False

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(user_input_mock.called)
        self.assertNotIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipython ... up to date', output)
        self.assertNotIn('ipdb', output)
        self.assertNotIn('celery ... upgrade available: 3.1.1 ==>', output)
        self.assertIn('Successfully upgraded', output)

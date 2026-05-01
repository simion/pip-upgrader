import os
import shutil
import tempfile
from io import StringIO
from subprocess import PIPE
from subprocess import Popen as popen
from unittest import TestCase
from unittest.mock import MagicMock, patch

import responses
from packaging.utils import canonicalize_name

from pip_upgrader import __version__ as VERSION
from pip_upgrader import cli
from pip_upgrader.packages_detector import PackagesDetector
from pip_upgrader.requirements_detector import RequirementsDetector

DEFAULT_OPTIONS = {
    '--dry-run': False,
    '--prerelease': False,
    '--skip-greater-equal': False,
    '--use-default-index': False,
    '--timeout': None,
    '--minor': False,
    '--patch': False,
    '--non-interactive': False,
    '--skip': [],
    '-p': [],
    '<requirements_file>': [],
}


def make_options(**overrides):
    opts = DEFAULT_OPTIONS.copy()
    opts.update(overrides)
    return opts


def mock_checkbox_select_all(*args, **kwargs):
    """Mock questionary.checkbox that selects all choices."""
    choices = kwargs.get('choices', [])
    values = [c.value for c in choices]
    result = MagicMock()
    result.unsafe_ask.return_value = values
    return result


def mock_checkbox_select_none(*args, **kwargs):
    """Mock questionary.checkbox that selects nothing."""
    result = MagicMock()
    result.unsafe_ask.return_value = []
    return result


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


@patch('pip_upgrader.packages_interactive_selector.questionary.checkbox', side_effect=mock_checkbox_select_all)
class TestCommand(TestCase):
    PACKAGE_NAMES = ['Django', 'celery', 'django-rest-auth', 'ipython']

    def _add_responses_mocks(self):
        for package in self.PACKAGE_NAMES:
            canonical = canonicalize_name(package)
            with open('tests/fixtures/{}.json'.format(package)) as fh:
                body = fh.read()

            responses.add(
                responses.GET,
                "https://pypi.python.org/pypi/{}/json".format(canonical),
                body=body,
                content_type="application/json",
            )

            with open('tests/fixtures/{}.html'.format(canonical)) as fh:
                body_html = fh.read()
            responses.add(responses.GET, "https://pypi.python.org/simple/{}/".format(canonical), body=body_html)

    def setUp(self):
        self._add_responses_mocks()

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '<requirements_file>': ['requirements.txt']}),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_basic_usage(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(checkbox_mock.called)

        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '<requirements_file>': ['requirements.txt']}),
    )
    @patch.dict('os.environ', {}, clear=False)
    def test_command_simple_html_index_url(self, options_mock, checkbox_mock):

        with (
            patch('sys.stdout', new_callable=StringIO) as stdout_mock,
            patch(
                'pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations',
                new=['pip.test.conf'],
            ),
        ):
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(checkbox_mock.called)
        self.assertIn('Setting API url', output)
        self.assertIn('https://pypi.python.org/simple/{package}', output)

        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '<requirements_file>': ['requirements.txt']}),
    )
    @patch.dict('os.environ', {'PIP_INDEX_URL': 'https://pypi.python.org/simple/'})
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_pip_index_url_environ(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(checkbox_mock.called)
        self.assertIn('Setting API url', output)
        self.assertIn('https://pypi.python.org/simple/{package}', output)

        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '--use-default-index': True, '<requirements_file>': ['requirements.txt']}
        ),
    )
    def test_command__use_default_index(self, options_mock, checkbox_mock):

        with (
            patch('sys.stdout', new_callable=StringIO) as stdout_mock,
            patch(
                'pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations',
                new=['pip.test.conf'],
            ),
        ):
            cli.main()
            output = stdout_mock.getvalue()

        self.assertNotIn('Setting API url', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '<requirements_file>': ['requirements.txt']}),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_interactive_no_selection(self, options_mock, checkbox_mock):
        checkbox_mock.side_effect = mock_checkbox_select_none

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(checkbox_mock.called)
        self.assertIn('No choice selected', output)
        self.assertNotIn('Setting API url', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '--non-interactive': True, '<requirements_file>': ['requirements.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_non_interactive_flag(self, options_mock, checkbox_mock):
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{
                '--dry-run': True,
                '--non-interactive': True,
                '--skip': ['^django$'],
                '<requirements_file>': ['requirements.txt'],
            }
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_non_interactive_with_skip(self, options_mock, checkbox_mock):
        """--non-interactive with --skip should upgrade all packages except the skipped ones."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        # django is skipped, django-rest-auth should still be upgraded
        dry_run_line = [line for line in output.split('\n') if 'Dry run complete' in line][0]
        self.assertNotIn('django', dry_run_line.lower().replace('django-rest-auth', ''))
        self.assertIn('django-rest-auth', dry_run_line.lower())
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{
                '--dry-run': True,
                '--non-interactive': True,
                '--skip': ['django.*'],
                '<requirements_file>': ['requirements.txt'],
            }
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_non_interactive_with_skip_regex(self, options_mock, checkbox_mock):
        """--skip with a wildcard regex should skip all matching packages."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        # both django and django-rest-auth match 'django.*', nothing left to upgrade
        self.assertIn('All packages are up-to-date. (skipped: Django, django-rest-auth)', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{
                '--dry-run': True,
                '--skip': ['^django$'],
                '<requirements_file>': ['requirements.txt'],
            }
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_interactive_with_skip(self, options_mock, checkbox_mock):
        """--skip should filter packages before the interactive prompt."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # checkbox was called (interactive mode) with django already filtered out
        self.assertTrue(checkbox_mock.called)
        dry_run_line = [line for line in output.split('\n') if 'Dry run complete' in line][0]
        # django (exact) is skipped; django-rest-auth should still appear
        self.assertNotIn('django', dry_run_line.lower().replace('django-rest-auth', ''))
        self.assertIn('django-rest-auth', dry_run_line.lower())
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{
                '--dry-run': True,
                '--non-interactive': True,
                '-p': ['django'],
                '<requirements_file>': ['requirements.txt'],
            }
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_non_interactive_overrides_p(self, options_mock, checkbox_mock):
        """--non-interactive should override -p and warn the user."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('Warning: --non-interactive overrides -p', output)
        # all packages upgraded, not just django
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['requirements.txt']}),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_not_interactive_all_packages(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertNotIn('ipdb', output)

        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['^django$'], '<requirements_file>': ['requirements.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_not_interactive_specific_package(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipdb', output)

        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['ipython'], '<requirements_file>': ['requirements.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_not_interactive_all_packages_up_to_date(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertNotIn('Setting API url', output)
        self.assertIn('All packages are up-to-date.', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['requirements/production.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_not_interactive_explicit_requirements(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertNotIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipdb', output)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)

        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['requirements/local.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_not_recursive_requirements_include(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)
        self.assertIn('requirements/local.txt', output)
        self.assertIn('requirements/production.txt', output)
        self.assertIn('requirements/extra/debug.txt', output)
        self.assertIn('requirements/extra/debug2.txt', output)
        self.assertNotIn('requirements/extra/bad_file.txt', output)

        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['^django$'], '--prerelease': True, '<requirements_file>': ['requirements.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_not_specific_package_prerelease(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)

        self.assertNotIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==> 1.11', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipdb', output)

        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['^django$'], '--prerelease': True, '<requirements_file>': ['requirements.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    def test_command_not_specific_package_prerelease_html_api(self, options_mock, checkbox_mock):

        with (
            patch('sys.stdout', new_callable=StringIO) as stdout_mock,
            patch(
                'pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations',
                new=['pip.test.conf'],
            ),
        ):
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)

        self.assertIn('Setting API url', output)
        self.assertIn('Django ... upgrade available: 1.10 ==> 1.11', output)
        self.assertNotIn('django-rest-auth', output)
        self.assertNotIn('ipdb', output)

        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '--timeout': '30', '<requirements_file>': ['requirements.txt']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_with_custom_timeout(self, options_mock, checkbox_mock):

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertTrue(checkbox_mock.called)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{
                '--dry-run': True,
                '-p': ['all'],
                '<requirements_file>': ['requirements/production.txt', 'requirements/extra/debug.txt'],
            }
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_multiple_files_same_package(self, options_mock, checkbox_mock):
        """Test that the same package across multiple files doesn't cause duplicate upgrades."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)
        self.assertIn('Dry run complete', output)
        # celery should only appear once in the success message
        success_line = [line for line in output.split('\n') if 'Dry run complete' in line][0]
        self.assertEqual(success_line.count('celery'), 1)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['requirements.txt']}),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_dash_package_names(self, options_mock, checkbox_mock):
        """Test that packages with dashes in their names are resolved correctly."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{
                '--dry-run': True,
                '-p': ['all'],
                '<requirements_file>': ['requirements.txt'],
                '--skip-greater-equal': True,
            }
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_skip_greater_equal(self, options_mock, checkbox_mock):
        """Test that --skip-greater-equal skips >= pinned packages."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        # Django==1.10 uses == so it should still be found
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch('pip_upgrader.cli.get_options', return_value=make_options(**{'--dry-run': True}))
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_autodetect_requirements(self, options_mock, checkbox_mock):
        """Test that requirements files are auto-detected when none specified."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertIn('Found valid requirements file(s)', output)
        self.assertIn('requirements.txt', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['tests/fixtures/sample_pyproject.toml']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_pyproject_toml(self, options_mock, checkbox_mock):
        """Test upgrading packages from pyproject.toml."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['tests/fixtures/sample_pyproject.toml']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_pyproject_toml_version_replacement(self, options_mock, checkbox_mock):
        """Test that pyproject.toml versions are actually updated in the file."""
        tmpdir = tempfile.mkdtemp()
        tmp_pyproject = tmpdir + '/pyproject.toml'
        shutil.copy('tests/fixtures/sample_pyproject.toml', tmp_pyproject)

        options_mock.return_value = make_options(
            **{
                '--dry-run': False,
                '-p': ['all'],
                '<requirements_file>': [tmp_pyproject],
            }
        )

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        with open(tmp_pyproject) as f:
            content = f.read()

        self.assertNotIn('Django==1.10', content)
        self.assertNotIn('django-rest-auth[with_social]==0.9.0', content)
        self.assertNotIn('celery==3.1.1', content)
        self.assertIn('Django==', content)
        self.assertIn('celery==', content)
        self.assertIn('Updated versions', output)
        self.assertIn('uv sync', output)
        # Verify green ANSI coloring
        self.assertIn('\033[32m', output)

        shutil.rmtree(tmpdir)


class TestVersionRanges(TestCase):
    """Tests for version range handling (e.g., >=8.1,<9)."""

    def test_expand_package_strips_upper_bound(self):
        """_expand_package should strip upper bound from version ranges."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options())
        name, vers, _pin = detector._expand_package('click>=8.1,<9')
        self.assertEqual(name, 'click')
        self.assertEqual(vers, '8.1')

    def test_expand_package_strips_complex_upper_bound(self):
        """_expand_package should handle complex upper bounds like >=2.0.0,<3.0.0."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options())
        name, vers, _pin = detector._expand_package('requests>=2.25.0,<3.0.0')
        self.assertEqual(name, 'requests')
        self.assertEqual(vers, '2.25.0')

    def test_expand_package_eq_no_upper_bound(self):
        """_expand_package should work normally for == pins."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options())
        name, vers, _pin = detector._expand_package('Django==1.10')
        self.assertEqual(name, 'Django')
        self.assertEqual(vers, '1.10')

    def test_expand_package_skips_gte_when_flag_set(self):
        """_expand_package should skip >= pins when --skip-greater-equal is set."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options(**{'--skip-greater-equal': True}))
        name, vers, _pin = detector._expand_package('click>=8.1,<9')
        self.assertIsNone(name)
        self.assertIsNone(vers)

    def test_upgrader_preserves_upper_bound(self):
        """PackagesUpgrader should replace version but preserve upper bound constraint."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'click', 'latest_version': '8.2.0'}
        result = upgrader._maybe_update_line_package('click>=8.1,<9\n', package)
        self.assertEqual(result, 'click>=8.2.0,<9\n')

    def test_upgrader_preserves_complex_upper_bound(self):
        """PackagesUpgrader should preserve complex upper bounds."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'requests', 'latest_version': '2.31.0'}
        result = upgrader._maybe_update_line_package('requests>=2.25.0,<3.0.0\n', package)
        self.assertEqual(result, 'requests>=2.31.0,<3.0.0\n')

    def test_upgrader_eq_unchanged(self):
        """PackagesUpgrader should handle == pins normally."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'Django', 'latest_version': '4.2.0'}
        result = upgrader._maybe_update_line_package('Django==1.10\n', package)
        self.assertEqual(result, 'Django==4.2.0\n')

    def test_upgrader_with_extras_and_upper_bound(self):
        """PackagesUpgrader should handle extras with upper bounds."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'uvicorn', 'latest_version': '0.30.0'}
        result = upgrader._maybe_update_line_package('uvicorn[standard]>=0.20.0,<1.0\n', package)
        self.assertEqual(result, 'uvicorn[standard]>=0.30.0,<1.0\n')

    def test_expand_package_with_extras_and_upper_bound(self):
        """_expand_package should handle extras with upper bounds."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options())
        name, vers, _pin = detector._expand_package('uvicorn[standard]>=0.20.0,<1.0')
        self.assertEqual(name, 'uvicorn')
        self.assertEqual(vers, '0.20.0')


class TestPyprojectDetection(TestCase):
    """Tests for pyproject.toml detection and parsing."""

    def test_requirements_detector_accepts_pyproject(self):
        """RequirementsDetector should accept a valid pyproject.toml."""
        detector = RequirementsDetector(['tests/fixtures/sample_pyproject.toml'])
        self.assertIn('tests/fixtures/sample_pyproject.toml', detector.get_filenames())

    def test_requirements_detector_rejects_pyproject_without_deps(self):
        """RequirementsDetector should reject pyproject.toml without [project.dependencies]."""
        detector = RequirementsDetector(['tests/fixtures/no_deps_pyproject.toml'])
        self.assertEqual(detector.get_filenames(), [])

    def test_packages_detector_parses_pyproject_dependencies(self):
        """PackagesDetector should extract pinned deps from pyproject.toml."""
        detector = PackagesDetector(['tests/fixtures/sample_pyproject.toml'])
        packages = detector.get_packages()
        self.assertIn('Django==1.10', packages)
        self.assertIn('django-rest-auth[with_social]==0.9.0', packages)
        self.assertIn('celery==3.1.1', packages)
        self.assertIn('ipython==6.0.0', packages)
        self.assertNotIn('pytest', packages)

    def test_packages_detector_skips_env_markers(self):
        """PackagesDetector should strip environment markers from deps."""
        tmpdir = tempfile.mkdtemp()
        tmp_pyproject = tmpdir + '/pyproject.toml'
        with open(tmp_pyproject, 'w') as f:
            f.write('[project]\nname = "test"\ndependencies = [\n    "tomli>=1.0.0; python_version < \\"3.11\\"",\n]\n')
        detector = PackagesDetector([tmp_pyproject])
        packages = detector.get_packages()
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0], 'tomli>=1.0.0')
        shutil.rmtree(tmpdir)

    def test_packages_detector_mixed_files(self):
        """PackagesDetector should handle a mix of requirements.txt and pyproject.toml."""
        detector = PackagesDetector(['requirements.txt', 'tests/fixtures/sample_pyproject.toml'])
        packages = detector.get_packages()
        self.assertIn('Django==1.10', packages)
        self.assertIn('celery==3.1.1', packages)


class TestPoetrySupport(TestCase):
    """Tests for Poetry pyproject.toml support."""

    def test_requirements_detector_accepts_poetry_pyproject(self):
        """RequirementsDetector should accept a pyproject.toml with [tool.poetry.dependencies]."""
        detector = RequirementsDetector(['tests/fixtures/poetry_pyproject.toml'])
        self.assertIn('tests/fixtures/poetry_pyproject.toml', detector.get_filenames())

    def test_requirements_detector_rejects_poetry_pyproject_without_deps(self):
        """RequirementsDetector should reject a Poetry pyproject.toml without dependencies."""
        detector = RequirementsDetector(['tests/fixtures/no_poetry_deps_pyproject.toml'])
        self.assertEqual(detector.get_filenames(), [])

    def test_packages_detector_parses_poetry_dependencies(self):
        """PackagesDetector should extract pinned deps from Poetry pyproject.toml."""
        detector = PackagesDetector(['tests/fixtures/poetry_pyproject.toml'])
        packages = detector.get_packages()
        # == and >= pins should be included
        self.assertIn('Django==1.10', packages)
        self.assertIn('celery>=3.1.1', packages)
        self.assertIn('ipython==6.0.0', packages)
        # python should be skipped
        python_pkgs = [p for p in packages if p.startswith('python')]
        self.assertEqual(python_pkgs, [])
        # caret (^) and wildcard (*) should be skipped
        flask_pkgs = [p for p in packages if 'flask' in p.lower()]
        self.assertEqual(flask_pkgs, [])
        unpinned_pkgs = [p for p in packages if 'unpinned' in p.lower()]
        self.assertEqual(unpinned_pkgs, [])

    def test_packages_detector_parses_poetry_dict_format(self):
        """PackagesDetector should handle Poetry dict format deps with extras."""
        detector = PackagesDetector(['tests/fixtures/poetry_pyproject.toml'])
        packages = detector.get_packages()
        # Dict format with extras
        self.assertIn('django-rest-auth[with_social]==0.9.0', packages)

    def test_packages_detector_parses_poetry_groups(self):
        """PackagesDetector should extract deps from Poetry dependency groups."""
        detector = PackagesDetector(['tests/fixtures/poetry_pyproject.toml'])
        packages = detector.get_packages()
        # ruff from [tool.poetry.group.dev.dependencies] with == pin
        self.assertIn('ruff==0.1.0', packages)
        # pytest from [tool.poetry.group.test.dependencies] has ^ pin, should be skipped
        pytest_pkgs = [p for p in packages if p.startswith('pytest')]
        self.assertEqual(pytest_pkgs, [])

    def test_upgrader_poetry_string_format(self):
        """PackagesUpgrader should update Poetry string format versions."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'Django', 'latest_version': '4.2.0'}
        result = upgrader._maybe_update_line_package('Django = "==1.10"\n', package)
        self.assertEqual(result, 'Django = "==4.2.0"\n')

    def test_upgrader_poetry_string_gte_format(self):
        """PackagesUpgrader should update Poetry >= string format versions."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'celery', 'latest_version': '5.3.0'}
        result = upgrader._maybe_update_line_package('celery = ">=3.1.1"\n', package)
        self.assertEqual(result, 'celery = ">=5.3.0"\n')

    def test_upgrader_poetry_string_gte_with_upper_bound(self):
        """PackagesUpgrader should preserve upper bound in Poetry format."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'requests', 'latest_version': '2.31.0'}
        result = upgrader._maybe_update_line_package('requests = ">=2.25.0,<3.0.0"\n', package)
        self.assertEqual(result, 'requests = ">=2.31.0,<3.0.0"\n')

    def test_upgrader_poetry_dict_format(self):
        """PackagesUpgrader should update Poetry dict format versions."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'django-rest-auth', 'latest_version': '1.0.0'}
        result = upgrader._maybe_update_line_package(
            'django-rest-auth = {version = "==0.9.0", extras = ["with_social"]}\n', package
        )
        self.assertEqual(result, 'django-rest-auth = {version = "==1.0.0", extras = ["with_social"]}\n')

    def test_upgrader_poetry_dict_gte_format(self):
        """PackagesUpgrader should update Poetry dict format with >= versions."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'uvicorn', 'latest_version': '0.30.0'}
        result = upgrader._maybe_update_line_package(
            'uvicorn = {version = ">=0.20.0,<1.0", extras = ["standard"]}\n', package
        )
        self.assertEqual(result, 'uvicorn = {version = ">=0.30.0,<1.0", extras = ["standard"]}\n')

    def test_upgrader_poetry_skip_gte(self):
        """PackagesUpgrader should skip >= pins in Poetry format when --skip-greater-equal is set."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options(**{'--skip-greater-equal': True}))
        package = {'name': 'celery', 'latest_version': '5.3.0'}
        result = upgrader._maybe_update_line_package('celery = ">=3.1.1"\n', package)
        self.assertEqual(result, 'celery = ">=3.1.1"\n')  # unchanged


@patch('pip_upgrader.packages_interactive_selector.questionary.checkbox', side_effect=mock_checkbox_select_all)
class TestPoetryIntegration(TestCase):
    """Integration tests for Poetry pyproject.toml support."""

    PACKAGE_NAMES = ['Django', 'celery', 'django-rest-auth', 'ipython']

    def _add_responses_mocks(self):
        for package in self.PACKAGE_NAMES:
            canonical = canonicalize_name(package)
            with open('tests/fixtures/{}.json'.format(package)) as fh:
                body = fh.read()

            responses.add(
                responses.GET,
                "https://pypi.python.org/pypi/{}/json".format(canonical),
                body=body,
                content_type="application/json",
            )

    def setUp(self):
        self._add_responses_mocks()

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['tests/fixtures/poetry_pyproject.toml']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_poetry_pyproject(self, options_mock, checkbox_mock):
        """Test upgrading packages from a Poetry pyproject.toml."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': False, '-p': ['all'], '<requirements_file>': ['tests/fixtures/poetry_pyproject.toml']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_poetry_pyproject_version_replacement(self, options_mock, checkbox_mock):
        """Test that Poetry pyproject.toml versions are actually updated in the file."""
        tmpdir = tempfile.mkdtemp()
        tmp_pyproject = tmpdir + '/pyproject.toml'
        shutil.copy('tests/fixtures/poetry_pyproject.toml', tmp_pyproject)

        options_mock.return_value = make_options(
            **{
                '--dry-run': False,
                '-p': ['all'],
                '<requirements_file>': [tmp_pyproject],
            }
        )

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        with open(tmp_pyproject) as f:
            content = f.read()

        # Old versions should be replaced
        self.assertNotIn('"==1.10"', content)
        self.assertNotIn('"==0.9.0"', content)
        self.assertNotIn('">=3.1.1"', content)
        # New versions should be present
        self.assertIn('Django = "==', content)
        self.assertIn('celery = ">=', content)
        # Caret/wildcard packages should remain untouched
        self.assertIn('flask = "^2.0"', content)
        self.assertIn('some-unpinned = "*"', content)
        # Output should confirm success
        self.assertIn('Updated versions', output)

        shutil.rmtree(tmpdir)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['tests/fixtures/poetry_pyproject.toml']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_poetry_mixed_with_requirements(self, options_mock, checkbox_mock):
        """Test upgrading from both requirements.txt and Poetry pyproject.toml."""
        options_mock.return_value = make_options(
            **{
                '--dry-run': True,
                '-p': ['all'],
                '<requirements_file>': ['requirements.txt', 'tests/fixtures/poetry_pyproject.toml'],
            }
        )

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('Dry run complete', output)  # end of TestPoetryIntegration


class TestOverlappingPackageNames(TestCase):
    """Tests for issue #61: overlapping package name regex."""

    def test_upgrader_does_not_match_substring_package(self):
        """Upgrading 'openai' should NOT modify 'opentelemetry-instrumentation-openai'."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'openai', 'latest_version': '1.50.0'}
        result = upgrader._maybe_update_line_package('opentelemetry-instrumentation-openai==1.0.0\n', package)
        self.assertEqual(result, 'opentelemetry-instrumentation-openai==1.0.0\n')  # unchanged

    def test_upgrader_does_match_exact_package(self):
        """Upgrading 'openai' SHOULD modify 'openai==1.0.0'."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'openai', 'latest_version': '1.50.0'}
        result = upgrader._maybe_update_line_package('openai==1.0.0\n', package)
        self.assertEqual(result, 'openai==1.50.0\n')

    def test_upgrader_does_not_match_substring_in_pyproject(self):
        """Upgrading 'openai' should NOT modify a pyproject.toml line with a longer name."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'openai', 'latest_version': '1.50.0'}
        result = upgrader._maybe_update_line_package('    "opentelemetry-instrumentation-openai==1.0.0",\n', package)
        self.assertEqual(result, '    "opentelemetry-instrumentation-openai==1.0.0",\n')

    def test_upgrader_does_not_match_substring_poetry(self):
        """Upgrading 'openai' should NOT modify Poetry lines with longer package names."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'openai', 'latest_version': '1.50.0'}
        result = upgrader._maybe_update_line_package('opentelemetry-instrumentation-openai = "==1.0.0"\n', package)
        self.assertEqual(result, 'opentelemetry-instrumentation-openai = "==1.0.0"\n')

    def test_upgrader_matches_package_with_extras(self):
        """Upgrading a package with extras should still work."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'openai', 'latest_version': '1.50.0'}
        result = upgrader._maybe_update_line_package('openai[embeddings]==1.0.0\n', package)
        self.assertEqual(result, 'openai[embeddings]==1.50.0\n')


class TestCompatibleRelease(TestCase):
    """Tests for ~= compatible release support (issue #34)."""

    def test_expand_package_tilde_equal(self):
        """_expand_package should handle ~= pins."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options())
        name, vers, pin_type = detector._expand_package('requests~=2.25.0')
        self.assertEqual(name, 'requests')
        self.assertEqual(vers, '2.25.0')
        self.assertEqual(pin_type, '~=')

    def test_expand_package_skips_tilde_when_skip_gte(self):
        """_expand_package should skip ~= pins when --skip-greater-equal is set."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options(**{'--skip-greater-equal': True}))
        name, vers, pin_type = detector._expand_package('requests~=2.25.0')
        self.assertIsNone(name)
        self.assertIsNone(vers)

    def test_compatible_upper_bound_three_parts(self):
        """~=1.2.3 should have upper bound 1.3."""
        from packaging.version import parse

        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        bound = PackagesStatusDetector._compute_compatible_upper_bound('1.2.3')
        self.assertEqual(bound, parse('1.3'))

    def test_compatible_upper_bound_two_parts(self):
        """~=1.2 should have upper bound 2."""
        from packaging.version import parse

        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        bound = PackagesStatusDetector._compute_compatible_upper_bound('1.2')
        self.assertEqual(bound, parse('2'))

    def test_upgrader_tilde_equal(self):
        """PackagesUpgrader should update ~= pins."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'requests', 'latest_version': '2.31.0'}
        result = upgrader._maybe_update_line_package('requests~=2.25.0\n', package)
        self.assertEqual(result, 'requests~=2.31.0\n')

    def test_upgrader_tilde_equal_skip_gte(self):
        """PackagesUpgrader should skip ~= pins when --skip-greater-equal is set."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options(**{'--skip-greater-equal': True}))
        package = {'name': 'requests', 'latest_version': '2.31.0'}
        result = upgrader._maybe_update_line_package('requests~=2.25.0\n', package)
        self.assertEqual(result, 'requests~=2.25.0\n')  # unchanged

    def test_packages_detector_includes_tilde_equal(self):
        """PackagesDetector should include ~= pinned deps from pyproject.toml."""
        tmpdir = tempfile.mkdtemp()
        tmp_pyproject = tmpdir + '/pyproject.toml'
        with open(tmp_pyproject, 'w') as f:
            f.write('[project]\nname = "test"\ndependencies = [\n    "requests~=2.25.0",\n]\n')
        detector = PackagesDetector([tmp_pyproject])
        packages = detector.get_packages()
        self.assertIn('requests~=2.25.0', packages)
        shutil.rmtree(tmpdir)

    def test_version_constraint_applied(self):
        """_apply_version_constraints should filter versions for ~= upper bound."""
        from packaging.version import parse

        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options())
        versions = [parse('2.25.0'), parse('2.31.0'), parse('3.0.0'), parse('3.1.0')]
        current = parse('2.25.0')
        max_ver = parse('3')
        result = detector._apply_version_constraints(versions, current, max_version=max_ver)
        self.assertEqual(result, [parse('2.25.0'), parse('2.31.0')])


class TestUpgradeConstraints(TestCase):
    """Tests for --minor and --patch upgrade constraints (issue #12)."""

    def test_patch_constraint_filters_versions(self):
        """--patch should only allow same major.minor versions."""
        from packaging.version import parse

        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options(**{'--patch': True}))
        versions = [parse('1.2.3'), parse('1.2.5'), parse('1.3.0'), parse('2.0.0')]
        current = parse('1.2.3')
        result = detector._apply_version_constraints(versions, current)
        self.assertEqual(result, [parse('1.2.3'), parse('1.2.5')])

    def test_minor_constraint_filters_versions(self):
        """--minor should only allow same major versions."""
        from packaging.version import parse

        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options(**{'--minor': True}))
        versions = [parse('1.2.3'), parse('1.3.0'), parse('2.0.0')]
        current = parse('1.2.3')
        result = detector._apply_version_constraints(versions, current)
        self.assertEqual(result, [parse('1.2.3'), parse('1.3.0')])

    def test_no_constraint_keeps_all(self):
        """No constraint should keep all versions."""
        from packaging.version import parse

        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options())
        versions = [parse('1.2.3'), parse('2.0.0'), parse('3.0.0')]
        current = parse('1.2.3')
        result = detector._apply_version_constraints(versions, current)
        self.assertEqual(result, [parse('1.2.3'), parse('2.0.0'), parse('3.0.0')])

    def test_combined_tilde_and_patch_constraint(self):
        """Both ~= upper bound and --patch should apply together."""
        from packaging.version import parse

        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        detector = PackagesStatusDetector([], make_options(**{'--patch': True}))
        versions = [parse('1.2.3'), parse('1.2.5'), parse('1.3.0'), parse('2.0.0')]
        current = parse('1.2.3')
        max_ver = parse('1.3')  # ~=1.2.3 upper bound
        result = detector._apply_version_constraints(versions, current, max_version=max_ver)
        self.assertEqual(result, [parse('1.2.3'), parse('1.2.5')])


class TestPythonVersionFiltering(TestCase):
    """Tests for filtering package versions by Python compatibility (issue #60)."""

    @responses.activate
    def test_filters_incompatible_python_versions(self):
        """Versions requiring a different Python should be excluded."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        # Build a fake PyPI JSON response with requires_python
        pypi_data = {
            'info': {'version': '3.0.0'},
            'releases': {
                '1.0.0': [{'upload_time': '2020-01-01T00:00:00', 'requires_python': None}],
                '2.0.0': [{'upload_time': '2021-01-01T00:00:00', 'requires_python': '>=3.8'}],
                '3.0.0': [{'upload_time': '2022-01-01T00:00:00', 'requires_python': '>=99.0'}],
            },
        }
        import json

        responses.add(
            responses.GET,
            'https://pypi.python.org/pypi/testpkg/json',
            body=json.dumps(pypi_data),
            content_type='application/json',
        )

        from packaging.version import parse

        detector = PackagesStatusDetector([], make_options())
        current = parse('1.0.0')
        status, reason = detector._fetch_index_package_info('testpkg', current)

        self.assertIsInstance(status, dict)
        # v3.0.0 requires Python >=99.0, so latest should be v2.0.0
        self.assertEqual(status['latest_version'], parse('2.0.0'))
        self.assertTrue(status['upgrade_available'])

    @responses.activate
    def test_no_requires_python_passes_through(self):
        """Versions without requires_python should not be filtered out."""
        from pip_upgrader.packages_status_detector import PackagesStatusDetector

        pypi_data = {
            'info': {'version': '2.0.0'},
            'releases': {
                '1.0.0': [{'upload_time': '2020-01-01T00:00:00'}],
                '2.0.0': [{'upload_time': '2021-01-01T00:00:00'}],
            },
        }
        import json

        responses.add(
            responses.GET,
            'https://pypi.python.org/pypi/testpkg2/json',
            body=json.dumps(pypi_data),
            content_type='application/json',
        )

        from packaging.version import parse

        detector = PackagesStatusDetector([], make_options())
        current = parse('1.0.0')
        status, reason = detector._fetch_index_package_info('testpkg2', current)

        self.assertIsInstance(status, dict)
        self.assertEqual(status['latest_version'], parse('2.0.0'))


class TestPipfileSupport(TestCase):
    """Tests for Pipfile (Pipenv) support."""

    def test_requirements_detector_accepts_pipfile(self):
        """RequirementsDetector should accept a valid Pipfile."""
        detector = RequirementsDetector(['tests/fixtures/Pipfile'])
        self.assertIn('tests/fixtures/Pipfile', detector.get_filenames())

    def test_requirements_detector_rejects_invalid_pipfile(self):
        """RequirementsDetector should reject a file named Pipfile without [packages]."""
        tmpdir = tempfile.mkdtemp()
        tmp_pipfile = tmpdir + '/Pipfile'
        with open(tmp_pipfile, 'w') as f:
            f.write('[requires]\npython_version = "3.10"\n')
        detector = RequirementsDetector([tmp_pipfile])
        self.assertEqual(detector.get_filenames(), [])
        shutil.rmtree(tmpdir)

    def test_requirements_detector_handles_non_utf8_encoding(self):
        """RequirementsDetector should not crash on requirements files with non-UTF-8 encoding (issue #72)."""
        detector = RequirementsDetector(['tests/fixtures/requirements_latin1.txt'])
        self.assertIn('tests/fixtures/requirements_latin1.txt', detector.get_filenames())

    def test_detect_inclusion_handles_non_utf8_encoding(self):
        """_detect_inclusion should handle non-UTF-8 encoded files without raising UnicodeDecodeError."""
        tmpdir = tempfile.mkdtemp()
        # Create a main requirements file that includes a latin-1 encoded sub-file
        included = os.path.join(tmpdir, 'requirements_base.txt')
        with open(included, 'wb') as f:
            # latin-1 encoded comment + a valid package line
            f.write(b'# D\xe9pendances\nDjango>=4.2\n')
        main = os.path.join(tmpdir, 'requirements.txt')
        with open(main, 'w') as f:
            f.write('-r requirements_base.txt\nrequests>=2.28\n')
        try:
            detector = RequirementsDetector([main])
            filenames = detector.get_filenames()
            self.assertIn(main, filenames)
            self.assertIn(included, filenames)
        finally:
            shutil.rmtree(tmpdir)

    def test_packages_detector_parses_pipfile(self):
        """PackagesDetector should extract pinned deps from Pipfile."""
        detector = PackagesDetector(['tests/fixtures/Pipfile'])
        packages = detector.get_packages()
        self.assertIn('Django==1.10', packages)
        self.assertIn('celery>=3.1.1', packages)
        self.assertIn('ipython==6.0.0', packages)
        # wildcard should be skipped
        flask_pkgs = [p for p in packages if 'flask' in p.lower()]
        self.assertEqual(flask_pkgs, [])
        ruff_pkgs = [p for p in packages if 'ruff' in p.lower()]
        self.assertEqual(ruff_pkgs, [])

    def test_packages_detector_parses_pipfile_dict_format(self):
        """PackagesDetector should handle Pipfile dict format with extras."""
        detector = PackagesDetector(['tests/fixtures/Pipfile'])
        packages = detector.get_packages()
        self.assertIn('django-rest-auth[with_social]==0.9.0', packages)

    def test_upgrader_pipfile_string_format(self):
        """PackagesUpgrader should update Pipfile string format versions."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'Django', 'latest_version': '4.2.0'}
        result = upgrader._maybe_update_line_package('Django = "==1.10"\n', package)
        self.assertEqual(result, 'Django = "==4.2.0"\n')

    def test_upgrader_pipfile_dict_format(self):
        """PackagesUpgrader should update Pipfile dict format versions."""
        from pip_upgrader.packages_upgrader import PackagesUpgrader

        upgrader = PackagesUpgrader([], [], make_options())
        package = {'name': 'django-rest-auth', 'latest_version': '1.0.0'}
        result = upgrader._maybe_update_line_package(
            'django-rest-auth = {version = "==0.9.0", extras = ["with_social"]}\n', package
        )
        self.assertEqual(result, 'django-rest-auth = {version = "==1.0.0", extras = ["with_social"]}\n')


@patch('pip_upgrader.packages_interactive_selector.questionary.checkbox', side_effect=mock_checkbox_select_all)
class TestPipfileIntegration(TestCase):
    """Integration tests for Pipfile support."""

    PACKAGE_NAMES = ['Django', 'celery', 'django-rest-auth', 'ipython']

    def _add_responses_mocks(self):
        for package in self.PACKAGE_NAMES:
            canonical = canonicalize_name(package)
            with open('tests/fixtures/{}.json'.format(package)) as fh:
                body = fh.read()
            responses.add(
                responses.GET,
                "https://pypi.python.org/pypi/{}/json".format(canonical),
                body=body,
                content_type="application/json",
            )

    def setUp(self):
        self._add_responses_mocks()

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': ['tests/fixtures/Pipfile']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_pipfile(self, options_mock, checkbox_mock):
        """Test upgrading packages from a Pipfile."""
        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        self.assertFalse(checkbox_mock.called)
        self.assertIn('Django ... upgrade available: 1.10 ==>', output)
        self.assertIn('django-rest-auth ... upgrade available: 0.9.0 ==>', output)
        self.assertIn('celery ... upgrade available: 3.1.1 ==>', output)
        self.assertIn('Dry run complete', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(
            **{'--dry-run': False, '-p': ['all'], '<requirements_file>': ['tests/fixtures/Pipfile']}
        ),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_command_pipfile_version_replacement(self, options_mock, checkbox_mock):
        """Test that Pipfile versions are actually updated in the file."""
        tmpdir = tempfile.mkdtemp()
        tmp_pipfile = tmpdir + '/Pipfile'
        shutil.copy('tests/fixtures/Pipfile', tmp_pipfile)

        options_mock.return_value = make_options(
            **{
                '--dry-run': False,
                '-p': ['all'],
                '<requirements_file>': [tmp_pipfile],
            }
        )

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        with open(tmp_pipfile) as f:
            content = f.read()

        # Old versions should be replaced
        self.assertNotIn('"==1.10"', content)
        self.assertNotIn('"==0.9.0"', content)
        self.assertNotIn('">=3.1.1"', content)
        # New versions should be present
        self.assertIn('Django = "==', content)
        self.assertIn('celery = ">=', content)
        # Wildcard packages should remain untouched
        self.assertIn('flask = "*"', content)
        self.assertIn('ruff = "*"', content)
        # Output should confirm success
        self.assertIn('Updated versions', output)

        shutil.rmtree(tmpdir)


@patch('pip_upgrader.packages_interactive_selector.questionary.checkbox', side_effect=mock_checkbox_select_all)
class TestYankedVersions(TestCase):
    """Test that yanked PyPI versions are excluded from upgrade suggestions."""

    YANKED_PYPI_RESPONSE = {
        "info": {
            "version": "0.89.0",
            "name": "fake-package",
        },
        "releases": {
            "0.88.0": [
                {
                    "upload_time": "2025-01-01T00:00:00",
                    "requires_python": None,
                    "yanked": False,
                    "yanked_reason": None,
                }
            ],
            "0.89.0": [
                {
                    "upload_time": "2025-02-01T00:00:00",
                    "requires_python": None,
                    "yanked": False,
                    "yanked_reason": None,
                }
            ],
            "1.0.0": [
                {
                    "upload_time": "2025-03-01T00:00:00",
                    "requires_python": None,
                    "yanked": True,
                    "yanked_reason": "wrong version",
                },
                {
                    "upload_time": "2025-03-01T00:00:00",
                    "requires_python": None,
                    "yanked": True,
                    "yanked_reason": "wrong version",
                },
            ],
        },
    }

    def _setup_requirements(self):
        self.tmpdir = tempfile.mkdtemp()
        self.req_file = os.path.join(self.tmpdir, 'requirements.txt')
        with open(self.req_file, 'w') as f:
            f.write('fake-package==0.88.0\n')

    def _add_responses_mock(self):
        import json

        responses.add(
            responses.GET,
            "https://pypi.python.org/pypi/fake-package/json",
            body=json.dumps(self.YANKED_PYPI_RESPONSE),
            content_type="application/json",
        )

    def setUp(self):
        self._add_responses_mock()
        self._setup_requirements()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '-p': ['all'], '<requirements_file>': []}),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_yanked_version_excluded(self, options_mock, checkbox_mock):
        """Yanked versions should not be suggested as upgrades (GH-73)."""
        options_mock.return_value = make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': [self.req_file]}
        )

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # Should upgrade to 0.89.0 (latest non-yanked), NOT 1.0.0 (yanked)
        self.assertIn('upgrade available: 0.88.0 ==> 0.89.0', output)
        self.assertNotIn('1.0.0', output)

    @responses.activate
    @patch(
        'pip_upgrader.cli.get_options',
        return_value=make_options(**{'--dry-run': True, '-p': ['all'], '<requirements_file>': []}),
    )
    @patch.dict('os.environ', {}, clear=False)
    @patch('pip_upgrader.packages_status_detector.PackagesStatusDetector.pip_config_locations', new=[])
    def test_partially_yanked_version_included(self, options_mock, checkbox_mock):
        """A version where only some files are yanked should still be included."""
        import json

        partial_response = json.loads(json.dumps(self.YANKED_PYPI_RESPONSE))
        # Make one file in 1.0.0 not yanked (partial yank)
        partial_response['releases']['1.0.0'][0]['yanked'] = False

        responses.replace(
            responses.GET,
            "https://pypi.python.org/pypi/fake-package/json",
            body=json.dumps(partial_response),
            content_type="application/json",
        )

        options_mock.return_value = make_options(
            **{'--dry-run': True, '-p': ['all'], '<requirements_file>': [self.req_file]}
        )

        with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
            cli.main()
            output = stdout_mock.getvalue()

        # 1.0.0 should be suggested because not ALL files are yanked
        self.assertIn('upgrade available: 0.88.0 ==> 1.0.0', output)

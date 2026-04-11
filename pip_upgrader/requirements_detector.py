import mimetypes
import os

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


class RequirementsDetector(object):
    """Takes raw requirements argument, and detects / discovers all the requirements files."""

    filenames = []

    def __init__(self, requirements_arg):
        self.filenames = []

        if not requirements_arg:
            self.autodetect_files()
        else:
            self.detect_files(requirements_arg)

    def get_filenames(self):
        """Returns a list of all filenames detected as proper requirements files."""
        return self.filenames

    def detect_files(self, requirements_arg):
        for argument in requirements_arg:
            if argument.endswith('pyproject.toml'):
                if self._is_valid_pyproject(argument):
                    self.filenames.append(argument)
                else:  # pragma: nocover
                    print('Invalid pyproject.toml (no [project.dependencies]): {}'.format(argument))
            elif os.path.basename(argument) == 'Pipfile':
                if self._is_valid_pipfile(argument):
                    self.filenames.append(argument)
                else:  # pragma: nocover
                    print('Invalid Pipfile (no [packages]): {}'.format(argument))
            elif self._is_valid_requirements_file(argument):
                self.filenames.append(argument)
            else:  # pragma: nocover
                print('Invalid requirements file: {}'.format(argument))
        self._check_inclusions_recursively()

    def autodetect_files(self):
        """Attempt to detect requirements files in the current working directory"""
        if self._is_valid_pyproject('pyproject.toml'):
            self.filenames.append('pyproject.toml')

        if self._is_valid_pipfile('Pipfile'):
            self.filenames.append('Pipfile')

        for candidate in ['requirements.txt', 'requirements.pip', 'requirements.in']:
            if self._is_valid_requirements_file(candidate):
                self.filenames.append(candidate)

        if os.path.isdir('requirements'):
            for filename in sorted(os.listdir('requirements')):
                file_path = os.path.join('requirements', filename)
                if self._is_valid_requirements_file(file_path):
                    self.filenames.append(file_path)
        self._check_inclusions_recursively()

    @staticmethod
    def _is_valid_requirements_file(filename):
        return os.path.isfile(filename) and mimetypes.guess_type(filename)[0] in ['text/plain', None]

    @staticmethod
    def _is_valid_pyproject(filename):
        """Check if file is a pyproject.toml with [project.dependencies] or [tool.poetry.dependencies]."""
        if not os.path.isfile(filename) or not filename.endswith('pyproject.toml'):
            return False
        try:
            with open(filename, 'rb') as f:
                data = tomllib.load(f)
            has_pep621 = 'dependencies' in data.get('project', {})
            has_poetry = 'dependencies' in data.get('tool', {}).get('poetry', {})
            return has_pep621 or has_poetry
        except Exception:
            return False

    @staticmethod
    def _is_valid_pipfile(filename):
        """Check if file is a Pipfile with [packages]."""
        if not os.path.isfile(filename) or not os.path.basename(filename) == 'Pipfile':
            return False
        try:
            with open(filename, 'rb') as f:
                data = tomllib.load(f)
            return 'packages' in data
        except Exception:
            return False

    def _check_inclusions_recursively(self):
        for filename in self.filenames:
            if not filename.endswith('pyproject.toml') and os.path.basename(filename) != 'Pipfile':
                self._detect_inclusion(filename)

    def _detect_inclusion(self, filename):
        with open(filename, encoding='utf-8', errors='surrogateescape') as fh:
            for line in fh:
                if line.strip().startswith('-r '):
                    included_filename = line.split('-r ')[1].strip()
                    included_filename = os.path.join(os.path.dirname(filename), included_filename)
                    if self._is_valid_requirements_file(included_filename) and included_filename not in self.filenames:
                        self.filenames.append(included_filename)
                        # recursively, check if the included file contains other inclusions
                        self._detect_inclusion(included_filename)

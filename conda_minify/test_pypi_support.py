from unittest.mock import patch
import yaml
import conda_minify

conda_dependencies = {
    "python": {'depends': ['libzlib >=1.2.13,<1.3.0a0']},
    "pip": {'depends': {'python': '>=3.7'}},

    "package-with-no-deps": {'depends': {}}
}
def my_read_conda_metadata(obj, pkg):
    retval = pkg.copy()
    retval.update(conda_dependencies.get(pkg["name"]))
    return retval

pypi_dependencies = {
    "numpy": {'depends': []},
}
def my_read_pypi_metadata(obj, pkg):
    retval = pkg.copy()
    retval.update(pypi_dependencies.get(pkg["name"]))
    return retval

#
# TODO: Verifying the final yaml can probably be done more
# sophistically by comparing structures. However, I did
# not find any obvious light-weighted mechanism, so for
# this simple test the assertions are stepwise and manual
#

@patch.object(conda_minify.CondaEnvironment, "_init_from_name", new=lambda *args: None)
@patch.object(conda_minify.CondaEnvironment, "read_pypi_metadata", new=my_read_pypi_metadata)
@patch.object(conda_minify.CondaEnvironment, "read_conda_metadata", new=my_read_conda_metadata)
class TestPipSupport:

    @classmethod
    @patch.object(conda_minify.CondaEnvironment, "get_conda_env_json")
    def _build_from_conda_env(clz, env, fake_get_conda_env_json):
        fake_get_conda_env_json.return_value = env
        condaenv = conda_minify.CondaEnvironment(name="testenv")
        condaenv.build_graph()
        return yaml.safe_load(condaenv.minify_requirements())

    def test_only_python_new(self):
        yml = TestPipSupport._build_from_conda_env(
            [
                {"channel": "conda-forge",
                "dist_name": "python-3.9.18-hfa1ae8a_0_cpython",
                "name": "python",
                "version": "3.9.18"
                }
            ]
        )
        assert len(yml["dependencies"]) == 1
        assert yml["dependencies"][0]=="python=3.9.18"

    def test_single_package_without_deps(self):
        '''Verify that a package with no deps in "any direction" is included'''
        yml = TestPipSupport._build_from_conda_env(
            [
                {"channel": "conda-forge",
                "dist_name": "package-with-no-deps.0.0.0-testcase",
                "name": "package-with-no-deps",
                "version": "0.0.0"
                }
            ]
        )
        assert len(yml["dependencies"]) == 1
        assert yml["dependencies"][0]=="package-with-no-deps=0.0.0"

    def test_python_and_pip(self):
        '''Verify that pip (which depends on python) shadows python'''

        yml = TestPipSupport._build_from_conda_env(
            [
                {"channel": "conda-forge",
                    "dist_name": "python-3.9.18-hfa1ae8a_0_cpython",
                    "name": "python", "version": "3.9.18"
                },
                {"channel": "conda-forge",
                    "dist_name": "pip-23.2.1-pyhd8ed1ab_0",
                    "name": "pip", "version": "23.2.1"
                }
            ]
        )
        assert len(yml["dependencies"]) == 1
        assert yml["dependencies"][0]=="pip=23.2.1"

    def test_numpy_from_pypi(self):
        '''Verify that numpy from pypi with no deps appears in output'''

        yml = TestPipSupport._build_from_conda_env(
            [
                {"channel": "conda-forge",
                    "dist_name": "python-3.9.18-hfa1ae8a_0_cpython",
                    "name": "python", "version": "3.9.18"
                },
                {"channel": "conda-forge",
                    "dist_name": "pip-23.2.1-pyhd8ed1ab_0",
                    "name": "pip", "version": "23.2.1"
                },
                {'channel': 'pypi',
                    'dist_name': 'numpy-1.26.0-pypi_0',
                    'name': 'numpy', 'version': '1.26.0'
                }
            ]
        )
        assert len(yml["dependencies"]) == 2
        assert yml["dependencies"][0]=="pip=23.2.1"
        assert isinstance(yml["dependencies"][1], dict)
        assert isinstance(yml["dependencies"][1]["pip"], list)
        assert len(yml["dependencies"][1]["pip"]) == 1
        assert yml["dependencies"][1]["pip"][0]=="numpy==1.26.0"

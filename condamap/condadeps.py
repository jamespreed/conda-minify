import pathlib
import sys
import json
import yaml
from collections import defaultdict
from conda.cli.python_api import run_command
from conda.exceptions import EnvironmentLocationNotFound
from .graph import DiGraph


class CondaEnvironment:
    """
    Imports a Conda environment specs and generates a minified version of
    the environment requirements.  This facilitates sharing environments 
    cross-platform when only the highest-level pacakges are really
    required.
    """

    def __init__(self, name=None, path=None):
        """
        Read in the packages and dependencies for the Conda environment `name`
        or located at `path`.

        :param name: the name of the Conda environment.
        :param path: the path to the Conda environment, use if the environment 
            is located in a directory not known by Conda.  If `name` is 
            passed, `path` is ignored.

        :type name: str
        :type path: str
        """
        self._name = None
        self._path = None
        self._env_packages_info = {}
        self._env_packages_name_map = {}
        self._pkgs_dirs = self.get_conda_pkgs_dirs()
        self.conda_graph = CondaGraph()

        if not name and not path:
            raise ValueError('Either the `name` or `path` of the Conda '
                'environment is required.')
        if name:
            self._init_from_name(name)
        elif path:
            self._init_from_path(path)
        self.load_package_metadata()
            
    def _init_from_name(self, name):
        try:
            header, _, _ = run_command('list', '-n', name, '_NOPACKAGE_')
        except EnvironmentLocationNotFound:
            raise
        self._name = name
        self._path = self._parse_list_header(header)

    def _init_from_path(self, path):
        try:
            header, _, _ = run_command('list', '-p', path, '_NOPACKAGE_')
        except EnvironmentLocationNotFound:
            raise
        path = self._parse_list_header(header)
        self._name = path.stem
        self._path = path

    def __contains__(self, item):
        return item in self._env_packages_name_map

    def get_conda_env_json(self):
        """
        Uses Conda to read the environment specs in json format.  Run if a
        change to the environment has been made after this object was 
        initialized.

        :returns: list[dict]
        """
        pkgs_str, _, _ = run_command('list', '-p', self.path, '--json')
        return json.loads(pkgs_str)

    def load_package_metadata(self):
        """
        Attempts to read package metadata from the unpackaged Conda binary or 
        from the Conda tarball for each of the packages in the environment.
        
        If the packages is from the PyPi channel, it will look for a PyPi
        metadata file to parse.

        Note: this will fail entirely if `conda clean` has been run.
        """
        for pkg in self.get_conda_env_json():
            name = pkg.get('name')
            simple = self._norm(name)
            self._env_packages_name_map.setdefault(name, name)
            self._env_packages_name_map.setdefault(simple, name)

            if pkg.get('channel') != 'pypi':
                p_info = self.read_conda_metadata(pkg)
            else:
                p_info = self.read_pypi_metadata(pkg)

            deps =  self._clean_requirments(p_info.get('depends', []))
            p_info['depends'] = deps
            p_info['simple_name'] = simple
            self._env_packages_info[name] = p_info

    def read_conda_metadata(self, pkg):
        """
        Search for the package's index.json file in the Conda `pkgs_dirs`
        locations.  Returns a copy of `pkg` with the updated metadata. 

        :param pkg: the package metadata, must include `dist_name`
        :type pkg: dict

        :returns: dict
        """
        paths = [
            d.joinpath(pkg['dist_name'], 'info', 'index.json')
            for d in self._pkgs_dirs
        ]
        # TODO: add/open archive files
        out = pkg.copy()
        for p in paths:
            if not p.exists():
                continue
            with p.open('r', encoding='utf8') as fp:
                out.update(json.load(fp))
            out.setdefault('conda_metadata_path', str(p))
            # just return the first hit
            return out
        return out

    def get_pypi_pkg_path(self, pkg):
        """
        This modifies the `pkg` in-place if the name has a dash.
        Returns the path to the PyPi metadata file or None.

        :param pkg: the package metadata, must include `name` and `version`
        :type pkg: dict
        :returns: pathlib.Path or None
        """
        pkg_name = pkg.get('name')
        pkg_version = pkg.get('version')
        # can't have a dash in the package directory, normally an underscore,
        # but occassionally some moron uses a dot
        for c in '_.':
            name = pkg_name.replace('-', c)
            path = self._path.joinpath(
                'Lib', 
                'site-packages', 
                '{0}-{1}.dist-info'.format(name, pkg_version),
                'METADATA'
            )
            if path.exists():
                return path
        return None

    def read_pypi_metadata(self, pkg):
        """
        Search for a PyPi package's METADATA file in the Lib/site-packages
        directory of the environment.

        :param pkg: the package metadata, must include `name` and `version`
        :type pkg: dict

        :returns: dict
        """
        out = pkg.copy()
        path = self.get_pypi_pkg_path(out)
        out.update({
            'pypi_metadata_path': '',
            'depends': []
        })
        if not path:
            return out
        with path.open('r', encoding='utf8') as fp:
            for line in fp:
                line = line.strip()
                # separate conditions to clean up multiline elif
                condition1 = line.startswith('Requires-Python')
                condition2 = (
                    line.startswith('Requires-Dist') 
                    and 'extra==' not in line.replace(' ', '')
                )
                condition3 = not line

                if condition1:
                    reqs = line.split(':')[-1].replace(' ', '')
                    out.get('depends').append('python ' + reqs)
                elif condition2:
                    reqs = line.split(':')[-1].split(';')[0]
                    reqs = reqs.replace('(', '').replace(')', '').strip()
                    out.get('depends').append(reqs)
                elif condition3:
                    break
        out['pypi_metadata_path'] = str(path)
        return out

    def _clean_requirments(self, reqs):
        """Clean up the requirements dicts"""
        if isinstance(reqs, dict):
            return reqs
        reqs_dict = {}
        for req in reqs:
            k, *v = req.split(' ', 1)
            reqs_dict.setdefault(self._norm(k), ''.join(v))
        return reqs_dict

    def _conda_name(self, pkg_name):
        """Attempt to find the name Conda uses for `pkg_name`"""
        simple = self._norm(pkg_name)
        name = self._env_packages_name_map.get(simple, '')
        return name

    def get_package(self, pkg_name):
        """
        Finds and returns the package information with `pkg_name`.

        :param pkg_name: the name of the package
        :type pkg_name: str
        """
        return self.env_packages_info.get(self._conda_name(pkg_name), {})

    def build_graph(self):
        """
        Builds the CondaGraph of package dependencies.
        """
        g = self.conda_graph = CondaGraph()
        for pkg in self.env_packages_info.values():
            g.add_connections(pkg.get('simple_name'), pkg.get('depends'))

    def minify_requirements(self, 
                            export_path=None,
                            include=None, 
                            exclude=None, 
                            add_versions='full',
                            add_builds=False):
        """
        Builds a minified version of the requirements YAML.

        :param export_path: The file path to write the minified requirements.
            If not passed, no file is written.
        :param include: The packages to include in the requirements.  Defaults 
            to including only the packages with top-level dependency.  Adding
            a dependency (lower level) package allows pinning the version,
            build, and channel.
        :param exclude: Packages to exclude from the requirments. Only removes 
            top-level dependency packages.  Useful for exporting computation
            without visualization.  I.e. ``exclude=['matplotlib']``.
        :param add_versions: Add part of or the full version to the 
            requirements. Allowed values are: 
              'full' or 'true' or True- Include the exact version
              'major' - Include the major value of the version only ('1.*')
              'minor' - Include the major and minor versions ('1.11.*')
              'none' or 'false' or False - Version not added.
        :param add_builds: Add the build number to the requirment, highly 
            specific and will override loosening of version requirements.

        :returns: yaml string

        :type export_path: path-like str
        :type include: list-like
        :type exclude: list-like
        :type add_version: str|bool
        :type add_builds: bool
        """
        # convert strings to lists, None to empty
        allowed = ('full', 'major', 'minor', 'none', 'true', 'false')
        add_versions = str(add_versions).lower()
        if add_versions not in allowed:
            raise ValueError(
                "Argument `add_version` accepts the following "
                "values: {}".format(allowed)
            )
        how = add_versions
        if isinstance(include, str):
            include = [include]
        if isinstance(exclude, str):
            exclude = [exclude]
        if not include:
            include = []
        if not exclude:
            exclude = []
        include = set(c for c in map(self._conda_name, include) if c)
        exclude = set(c for c in map(self._conda_name, exclude) if c)

        req_names = set(map(self._conda_name, 
            self.conda_graph.get_highest_dependents()))
        req_names = req_names.union(include).difference(exclude)
        req_data = {k: self._env_packages_info[k] for k in req_names}

        conda_deps = {
            name: {
                'version': self._format_version(pkg.get('version'), how),
                'build_string': pkg.get('build_string'),
                'channel': pkg.get('channel')
            }
            for name, pkg in req_data.items()
            if pkg.get('channel') != 'pypi'
        }

        # set default channels first i guess?
        channels = set(d.get('channel') for d in conda_deps.values())
        channels = sorted(channels, key=lambda x: 'pkgs/' not in x)
        
        pip_deps = {
            name: {
                'version': self._format_version(pkg.get('version'), how),
                'build_string': pkg.get('build_string'),
                'channel': pkg.get('channel')
            }
            for name, pkg in req_data.items()
            if pkg.get('channel') == 'pypi'
        }

        conda_dep_str = '{name}'
        pip_dep_str = '{name}'
        if add_versions:
            conda_dep_str += '={version}'
            pip_dep_str += '=={version}'
        if add_builds:
            if not add_versions:
                conda_dep_str += '=*'
            conda_dep_str += '={build_string}'

        all_deps = [
            conda_dep_str.format(name=name, **pkg)
            for name, pkg in conda_deps.items()
        ]
        if pip_deps:
            all_deps += [{'pip': [
                pip_dep_str.format(name=name, **pkg)
                for name, pkg in pip_deps.items()
            ]}]

        env_data = {
            'name': self.name,
            'channels': channels,
            'dependencies': all_deps
        }

        yaml_str = yaml.dump(env_data, sort_keys=False)
        if export_path:
            with pathlib.Path(export_path).open('w') as fp:
                fp.write(yaml_str)
        return yaml_str

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return str(self._path.absolute())

    @property
    def pkgs_dirs(self):
        return tuple([str(p) for p in self._pkgs_dirs])

    @property
    def env_packages(self):
        return tuple(self._env_packages_info)

    @property
    def env_packages_info(self):
        info_keys = (
            'arch',
            'build_string', 
            'channel', 
            'depends', 
            'platform', 
            'simple_name',
            'subdir', 
            'version'
        )
        return {
            name: {k: pkg.get(k, '') for k in info_keys}
            for name, pkg in self._env_packages_info.items()
        }

    @property
    def env_packages_specs(self):
        s1 = '{name}=={version}[build={build_string}]'
        s2 = '{name}=={version}'
        return tuple([
            s2.format(**p) 
            if p.get('build_string').startswith('pypi')
            else s1.format(**p)
            for p in self._env_packages_info.values()
        ])

    @staticmethod
    def _norm(pkg_name):
        """Normalized a package name"""
        return str(pkg_name).lower().replace('-', '_').replace('.', '_')

    @staticmethod
    def _format_version(version, how):
        """
        Version string formatter for loosening version requirements.

        :param version: the version strings.
        :type version: str

        :param how: how to format the version. 
        :type how: str

        :returns: [str] formatted version string
        """
        _how = str(how).lower()
        allowed = ('full', 'major', 'minor', 'true')
        if _how not in allowed:
            raise ValueError(
                "Argument `how` only accepts the following values: {}".format(
                    allowed
                )
            )

        n = version.count('.')
        if (n == 0) or (_how=='full') or (_how=='true'):
            return version
        if n == 1:
            major, minor = version.split('.')
            subs = ''
        if version.count('.') >= 2:
            major, minor, subs = version.split('.', 2)

        if _how == 'major':
            return major + '.*'
        if _how == 'minor':
            if not subs:
                return '{0}.{1}'.format(major, minor)
            return '{0}.{1}.*'.format(major, minor)

    #TODO: add default channel extraction

    @staticmethod
    def get_conda_pkgs_dirs():
        """
        Uses the Conda Python API to retrieve the `pkgs_dirs` from the conda
        config file.
        """
        dirs_str, _, _ = run_command('config', '--show', 'pkgs_dirs', '--json')
        pkgs_dirs = [
            pathlib.Path(p)
            for p in
            json.loads(dirs_str).get('pkgs_dirs', [])
        ]
        return pkgs_dirs

    @staticmethod
    def _parse_list_header(header):
        path = pathlib.Path(
            header.split('\n')[0]
                  .replace('# packages in environment at', '')
                  .strip(': ')
        ).absolute()
        return path


class CondaGraph(DiGraph):

    def get_lowest_dependencies(self):
        """
        Returns a list of the packages which do not depend on any other 
        package in the environment.  These are the roots of the graph.
        """
        return [k for k in self._inward if not self._outward.get(k)]

    def get_highest_dependents(self):
        """
        Returns a list of packages which are not a dependency for another
        package in the environment.  These are the leaves of the graph.
        """
        return [k for k in self._outward if not self._inward.get(k)]

    def get_package_dependencies(self, pkg_name):
        """
        Returns the first-level dependecies of the package.
        """
        return self._outward.get(self._norm(pkg_name))

    def get_package_dependency_tree(self, pkg_name, max_depth=15):
        """
        Returns a hierarchy of all of the dependencies for the package.
        """
        if pkg_name not in self:
            return {}
        
        node = self._norm(pkg_name)
        out = defaultdict(set)
        out[0].add(node)
        dep_lvls = {}
            
        for depth in range(max_depth):
            for node in out.get(depth, set()).copy():
                deps = self.get_package_dependencies(node)
                if deps:
                    out[depth + 1].update(deps)
                # move all dependencies to lowest required level
                for dep in deps:
                    if dep in dep_lvls:
                        lvl = dep_lvls.get(dep)
                        out[lvl].discard(dep)
                # update latest level
                dep_lvls.update({dep: depth+1 for dep in deps})
        return dict(out)


class CondaImportError(ImportError):
    pass
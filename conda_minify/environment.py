import pathlib
import os
import glob
import json
import yaml
from collections import defaultdict
from conda.cli.python_api import run_command
from conda.exceptions import EnvironmentLocationNotFound
from .graph import DirectedAcyclicGraph


def format_version(version, how):
    """
    Version string formatter for loosening version requirements.

    :version: [str] the version strings.
    :how: [str|bool] how to format the version. 

    :returns: [str] formatted version string
    """
    _how = str(how).lower()
    allowed = ('full', 'major', 'minor', 'none')
    if _how not in allowed:
        raise ValueError(
            "Argument `how` only accepts the following values: {}".format(
                allowed
            )
        )

    n = version.count('.')
    if (n == 0) or (_how == 'full'):
        return version
    if n == 1:
        major, minor = version.split('.')
        subs = ''
    if n >= 2:
        major, minor, subs = version.split('.', 2)

    if _how == 'major':
        return major + '.*'
    if _how == 'minor':
        if not subs:
            return '{0}.{1}'.format(major, minor)
        return '{0}.{1}.*'.format(major, minor)
    return version

def get_conda_default_channels():
    """
    Uses the Conda Python API to retrieve the default channels from the conda
    config file.

    :returns: [list] the default channels used by the Conda executable.
    """
    channel_str, _, _ = run_command('config', '--show', 
        'default_channels', '--json')
    channels = json.loads(channel_str)
    return [c.get('name') for c in channels.get('default_channels', [])]

def get_conda_pkgs_dirs():
    """
    Uses the Conda Python API to retrieve the `pkgs_dirs` from the conda
    config file.

    :returns: [list] pathlib.Path objects for each path.
    """
    dirs_str, _, _ = run_command('config', '--show', 'pkgs_dirs', '--json')
    pkgs_dirs = [
        pathlib.Path(p)
        for p in
        json.loads(dirs_str).get('pkgs_dirs', [])
    ]
    return pkgs_dirs

def req_yaml_template(pip=False, version=True, build=False):
    """
    Builds a template string for requirement lines in the YAML format.

    :pip: [bool] Whether to build a Conda requirement line or a pip line
    :version: [bool] Includes the version template
    :build: [bool] Includes the build template.  Makes version "=*" if the 
        `version` is False for Conda packages.

    :returns: [str] The requirement string template.
    """
    template_str = '{name}'
    if version:
        template_str += '=={version}' if pip else '={version}'
    if build and not pip:
        if not version:
            template_str += '=*'
        template_str += '={build_string}'
    return template_str

class CondaEnvironment:
    """
    Imports a Conda environment specs and generates a minified version of
    the environment requirements.  This facilitates sharing environments 
    cross-platform when only the highest-level pacakges are really
    required.
    """

    _DEFAULT_CHANNELS = frozenset(['pkgs/main', 'pkgs/r', 'pkgs/msys2'])

    def __init__(self, name=None, path=None):
        """
        Read in the packages and dependencies for the Conda environment `name`
        or located at `path`.

        :name: [str] the name of the Conda environment.
        :path: [str] the path to the Conda environment, use if the environment 
            is located in a directory not known by Conda.  If `path` is 
            passed, `name` is ignored.
        """
        self._name = None
        self._path = None
        self._env_packages_info = {}
        self._env_packages_name_map = {}
        self._pkgs_dirs = get_conda_pkgs_dirs()
        self.conda_graph = CondaGraph()
        # I am restricing the default channels to those that are defined by
        # Anaconda.  Adding a channel to defaults does not mean another person
        # has added the same channel.
        _channels = set(get_conda_default_channels())
        _channels.intersection_update(self._DEFAULT_CHANNELS)
        self.default_channels = _channels

        if not name and not path:
            raise ValueError('Either the `name` or `path` of the Conda '
                'environment is required.')
        if path:
            self._init_from_path(path)
        elif name:
            self._init_from_name(name)

        self.pypi_root_path = self.get_pypi_root_path()
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

        :returns: [list] list of dictionaries containing package metadata
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

        :pkg: [dict] the package metadata, must include `dist_name`

        :returns: [dict] the package metadata including the Conda metadata.
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

    def get_pypi_root_path(self):
        """
        Returns the path to directory where PyPi metadata files resides, or None.

        :returns: [pathlib.Path|None]
        """
        python_pkg = None
        for pkg in self.get_conda_env_json():
            name = pkg.get('name')
            if name.lower() == "python":
                python_pkg = pkg
                break

        # no Python, no Pip...
        if python_pkg is None: return None

        python_versions = pkg['version'].split(".")
        while len(python_versions) > 0:
            pattern = str(self._path) + os.sep + "[Ll]ib"  # Big-L in Windows. little-l elsewhere
            pattern += os.sep + "python"+".".join(python_versions)
            python_versions.pop()
            pattern += os.sep + "site-packages"

            paths  = glob.glob(pattern)
            if len(paths)==1:
                return pathlib.Path(paths[0])
        return None

    def get_pypi_pkg_path(self, pkg):
        """
        This modifies the `pkg` in-place if the name has a dash.
        Returns the path to the PyPi metadata file or None.

        :pkg: [dict] the package metadata, must include `name` and `version`

        :returns: [pathlib.Path|None]
        """
        pkg_name = pkg.get('name')
        pkg_version = pkg.get('version')
        # can't have a dash in the package directory, normally an underscore,
        # but occassionally some moron uses a dot
        name = pkg_name.replace('-','[_.]')
    
        pattern = str(self.pypi_root_path) + os.sep
        pattern += f"{name}-{pkg_version}.dist-info" + os.sep
        pattern += "METADATA"
        paths  = glob.glob(pattern)
        if len(paths)==1:
            return pathlib.Path(paths[0])
        return None

    def read_pypi_metadata(self, pkg):
        """
        Search for a PyPi package's METADATA file in the Lib/site-packages
        directory of the environment.

        :pkg: [dict] the package metadata, must include `name` and `version`

        :returns: [dict] the package metadata including the PyPi metadata.
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

        :pkg_name: [str] the name of the package.

        :returns: [dict] dictionary of the package metadata.
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
                            add_exclusion_deps=False,
                            how='full',
                            add_builds=False):
        """
        Builds a minified version of the requirements spec in YAML format.

        :export_path: [str|Path]
            The file path to write the minified requirements. If not passed,
            no file is written.
        :include: [list-like]
            The packages to include in the requirements.  Defaults to
            including only the packages with top-level dependency.  Adding a
            dependency (lower level) package allows pinning the version, 
            build, and channel.
        :exclude: [list-like]
            Packages to exclude from the requirments. Only removes top-level 
            dependency packages.  Useful for exporting computation without 
            visualization.  E.g. ``exclude=['matplotlib']``.
        :add_exclusion_deps: [bool]
            Whether to add dependencies of excluded packages to the minified 
            spec.  E.g. using 
            ``exclude=['pandas'], add_exclusion_deps=True`` removes 'pandas' 
            from the spec, but adds 'numpy', 'python_dateutil', and 'pytz', 
            the next level of dependencies for pandas.
        :how: [str|bool]
            Controls how the version for each package is formatted. 
            Allowed values are: 
              'full' - Include the exact version
              'major' - Include the major value of the version only ('1.*')
              'minor' - Include the major and minor versions ('1.11.*')
              'none' - Version not added.
        :add_builds: [bool]
            Add the build number to the requirment, highly specific and will 
            override loosening of version requirements.

        :returns: [str]
            The YAML string for the environment spec.
        """
        # convert strings to lists, None to empty
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
        # add dependencies to the inclusions
        if add_exclusion_deps:
            for e in exclude:
                include.update(self.conda_graph.get_package_dependencies(e))

        req_names = set(map(self._conda_name, 
            self.conda_graph.highest_dependents()))
        req_names = req_names.union(include).difference(exclude)
        req_data = {k: self._env_packages_info[k] for k in req_names}

        env_data = self._construct_env_reqs(req_data)
        use_version = how.lower() != 'none'
        conda_str = req_yaml_template(False, use_version, add_builds)
        pip_str = req_yaml_template(True, use_version, add_builds)

        yaml_data = {
            'name': self.name,
            'channels': env_data.get('channels'),
            'dependencies': []
        }

        dependencies = yaml_data.get('dependencies')
        for name, pkg in env_data.get('conda_deps').items():
            version = format_version(pkg.get('version'), how)
            dependencies.append(
                conda_str.format(name=name, version=version, 
                    build_string=pkg.get('build_string'))
            )
        
        dependencies_pip = []
        for name, pkg in env_data.get('pip_deps').items():
            version = format_version(pkg.get('version'), how)
            dependencies_pip.append(
                pip_str.format(name=name, version=version)
            )
        if dependencies_pip:
            dependencies.append({'pip': dependencies_pip})

        yaml_str = yaml.dump(yaml_data, sort_keys=False)
        self._exporter(export_path, yaml_str)
        return yaml_str

    def relax_requirements(self, 
                           export_path=None, 
                           how='minor', 
                           pin=None, 
                           override=None):
        """
        Builds a requirement YAML for the entire environment with relaxed 
        requirements.

        :export_path: [str|Path]
            The file path to write the minified requirements. If not passed,
            no file is written.
        :how: [str|bool]
            The default method for how the requirements will be relaxed.  Using
            the `pin` or `override` arguments takes precedence over this value.
              'full' - Include the exact version
              'major' - Include the major value of the version only ('1.*')
              'minor' - Include the major and minor versions ('1.11.*')
              'none' - Version not added.
        :pin: [list]
            Which packages will have their full version pinned to the current
            version in the environment.  Packages not in the environment are
            ignored.
        :override: [dict]
            Keys are the package names; values are the `how` methods to use for
            that specific package.  The same package cannot be listed in `pin`
            and `override`.  Packages not in the environment are ignored.

        :returns: [str]
            The YAML string with relaxed requirements.
        """
        if isinstance(pin, str):
            pin = [pin]
        if not pin:
            pin = []
        if not override:
            override = {}

        pin = [self._conda_name(p) for p in pin if self._conda_name(p)]
        override = {
            self._conda_name(p): h
            for p, h in override.items()
            if self._conda_name(p)
        }
        for p in pin:
            if p in override:
                raise ValueError(
                    'The package "{0}" was referenced in both `pin` and '
                    '`override`.  Only one of these methods can be used per '
                    'package.'.format(p)
                )
        how_dict = {p: how for p in self.env_packages}
        how_dict.update({p: 'full' for p in pin})
        how_dict.update(override)

        env_data = self._construct_env_reqs(self.env_packages_info)
        conda_deps = env_data.get('conda_deps', {})
        pip_deps = env_data.get('pip_deps', {})
        yaml_data = {
            'name': self.name,
            'channels': env_data.get('channels'),
            'dependencies': []
        }

        dependencies = yaml_data.get('dependencies')
        for name, pkg in conda_deps.items():
            h = how_dict.get(name, 'false')
            use_version = how.lower() != 'none'
            req_str = req_yaml_template(False, use_version)
            version = format_version(pkg.get('version'), h)
            dependencies.append(req_str.format(name=name, version=version))

        dependencies_pip = []
        for name, pkg in pip_deps.items():
            h = how_dict.get(name, 'false')
            use_version = how.lower() != 'none'
            req_str = req_yaml_template(True, use_version)
            version = format_version(pkg.get('version'), h)
            dependencies_pip.append(req_str.format(name=name, version=version))
        if dependencies_pip:
            dependencies.append({'pip': dependencies_pip})
            
        yaml_str = yaml.dump(yaml_data, sort_keys=False)
        self._exporter(export_path, yaml_str)
        return yaml_str

    def _construct_env_reqs(self, packages):
        """
        Takes a dictionary of packages and returns a dictionary with
        environment info needed to construct the YAML.

        :packages: [dict] package name key; package info values

        :returns: [dict] 
        """
        conda_deps = {
            name: {
                'version': pkg.get('version'),
                'build_string': pkg.get('build_string'),
                'channel': pkg.get('channel')
            }
            for name, pkg in packages.items()
            if pkg.get('channel') != 'pypi'
        }
        
        pip_deps = {
            name: {
                'version': pkg.get('version'),
                'build_string': pkg.get('build_string'),
                'channel': pkg.get('channel')
            }
            for name, pkg in packages.items()
            if pkg.get('channel') == 'pypi'
        }

        # set default channels first i guess?
        channels = set(
            self._to_default(d.get('channel')) 
            for d in conda_deps.values()
        )
        channels = sorted(channels, key=lambda x: x!='defaults')

        env_data = {
            'name': self.name,
            'channels': channels,
            'conda_deps': conda_deps,
            'pip_deps': pip_deps
        }

        return env_data

    def _to_default(self, c):
        if c in self.default_channels:
            return 'defaults'
        return c

    def _exporter(self, export_path, x):
        if export_path:
            with pathlib.Path(export_path).open('w') as fp:
                fp.write(x)

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
            #'name',
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
    def _parse_list_header(header):
        path = pathlib.Path(
            header.split('\n')[0]
                  .replace('# packages in environment at', '')
                  .strip(': ')
        ).absolute()
        return path


class CondaGraph(DirectedAcyclicGraph):

    def lowest_dependencies(self):
        """
        Returns a list of the packages which do not depend on any other 
        package in the environment.  These are the roots of the graph.
        """
        return [k for k in self._inward if not self._outward.get(k)]

    def highest_dependents(self):
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
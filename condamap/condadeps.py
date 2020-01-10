import pathlib
import sys
import json
from collections import defaultdict
from conda.cli.python_api import run_command as run_conda
from conda.exceptions import EnvironmentLocationNotFound
from .graph import DiGraph


class CondaEnvironment:
    def __init__(self, name=None, path=None):
        """
        Read in the packages and dependencies for the Conda environment `name`
        or located at `path`.

        ::Paramters::
        name : the name of the Conda environment.
        path : the path to the Conda environment, use if the environment is 
            located in a directory known by Conda.  If `name` is passed,
            `path` is ignored.

        ::Types::
        name : str
        path : str
        """
        self._name = None
        self._path = None
        self._env_packages_raw = []
        self._env_packages_info = []
        self._pkgs_dirs = self.get_conda_pkgs_dirs()
        self.graph = CondaGraph()
        if not name and not path:
            raise ValueError('Either the `name` or `path` of the Conda '
                'environment is required.')
        if name:
            self._init_from_name(name)
        elif path:
            self._init_from_path(path)
        self.load_conda_json()
        self.load_package_metadata()
            
    def _init_from_name(self, name):
        try:
            header, _, _ = run_conda('list', '-n', name, '_NOPACKAGE_')
        except EnvironmentLocationNotFound:
            raise
        self._name = name
        self._path = self._parse_list_header(header)

    def _init_from_path(self, path):
        try:
            header, _, _ = run_conda('list', '-p', path, '_NOPACKAGE_')
        except EnvironmentLocationNotFound:
            raise
        path = self._parse_list_header(header)
        self._name = path.stem
        self._path = path

    def load_conda_json(self):
        """
        Uses Conda to read the environment specs in json format.  Run if a
        change to the environment has been made after this object was 
        initialized.
        """
        pkgs_str, _, _ = run_conda('list', '-p', self.path, '--json')
        self._env_packages_raw = json.loads(pkgs_str)

    def load_package_metadata(self):
        """
        Attempts to read package metadata from the unpackaged Conda binary or 
        from the Conda tarball for each of the packages in the environment.
        
        If the packages is from the PyPi channel, it will look for a PyPi
        metadata file to parse.

        Note: this will fail entirely if `conda clean` has been run.
        """
        env_packages_info = []
        for pkg in self._env_packages_raw:
            if pkg.get('channel') != 'pypi':
                p_info = self.read_conda_metadata(pkg)
            else:
                p_info = self.read_pypi_metadata_reqs(pkg)
            p_info['depends'] = self._clean_requirments(
                p_info.get('depends', [])
            )
            p_info['simple_name'] = self.normalize_name(
                p_info.get('name')
            )
            env_packages_info.append(p_info)
        self._env_packages_info = env_packages_info

    def read_conda_metadata(self, pkg):
        """
        Search for the package's index.json file in the Conda `pkgs_dirs`
        locations.  Returns a copy of `pkg` with the updated metadata. 
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

    def read_pypi_metadata_reqs(self, pkg):
        """
        Search for a PyPi package's METADATA file in the Lib/site-packages
        directory of the environment.
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
        if isinstance(reqs, dict):
            return reqs
        reqs_dict = {}
        for req in reqs:
            k, *v = req.split(' ', 1)
            reqs_dict.setdefault(self.normalize_name(k), ''.join(v))
        return reqs_dict

    def build_graph(self):
        """
        Builds the CondaGraph of package dependencies.
        """
        g = self.graph = CondaGraph()
        for pkg in self.env_packages_info.values():
            g.add_connections(pkg.get('simple_name'), pkg.get('depends'))

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
        return tuple([p.get('name') for p in self._env_packages_info])

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
            pkg.get('name'): {k: pkg.get(k, '') for k in info_keys}
            for pkg in self._env_packages_info
        }

    @property
    def env_packages_specs(self):
        s1 = '{name}=={version}[build={build_string}]'
        s2 = '{name}=={version}'
        return tuple([
            s2.format(**p) 
            if p.get('build_string').startswith('pypi')
            else s1.format(**p)
            for p in self._env_packages_info
        ])

    @staticmethod
    def normalize_name(pkg_name):
        return pkg_name.lower().replace('-', '_').replace('.', '_')

    @staticmethod
    def get_conda_pkgs_dirs():
        dirs_str, _, _ = run_conda('config', '--show', 'pkgs_dirs', '--json')
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
            for node in out.get(depth):
                deps = self.get_package_dependencies(node)
                out[depth + 1].update(deps)
                # move all dependencies to lowest required level
                for dep in deps:
                    if dep in dep_lvls:
                        lvl = dep_lvls.get(dep)
                        out[lvl].discard(dep)
                # update latest level
                dep_lvls.update({dep: depth+1 for dep in deps})
        return out
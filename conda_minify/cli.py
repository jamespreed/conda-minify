import argparse
import sys
import os
import textwrap as _textwrap
from argparse import HelpFormatter
from .environment import CondaEnvironment


class MyFormatter(HelpFormatter):
    def _split_lines(self, text, width):
        return [w for t in text.splitlines() 
                    for w in _textwrap.wrap(t, width)]

def main():
    parser = argparse.ArgumentParser(prog='conda-minify',
        description='Builds minimized Conda specs to share environments.',
        formatter_class=MyFormatter)
    main_group = parser.add_argument_group(
        title=':==== Main arguments ====',
        description='Options available to all methods within conda-minify.')
    main_group.add_argument('--name', '-n',
        help='The environment name to export. Defaults to using the current '
            'environment.  Including a forward or backslash will be '
            "interpretted as the environment's path.")
    main_group.add_argument('--relax', 
        action='store_true', 
        help='Switches to using the relax API to export the entire '
            'environment specs with relaxed versioning numbers.')
    main_group.add_argument('--how', default='minor',
        choices=['full', 'major', 'minor', 'none'],
        help='(default: minor)\nThe method for how requirement versions are '
            'added to the spec.\n'
            "- 'full': Include the exact version\n"
            "- 'major': Include the major value only ('1.*')\n"
            "- 'minor': Include the major and minor ('1.11.*')\n"
            "- 'none': Version is omitted\n"
            'Note: When using the --relax option:\n  The --pin and '
            '--override arguments takes precedence over this value.\n')
    main_group.add_argument('-f', '--file', default=None,
        help='The file path for export.  Default prints output to screen.')

    minify_group = parser.add_argument_group(
        title=':==== Minify arguments ====',
        description='Options exclusively available when using MINIFY (the '
            'default) to export an environment specification.  These are '
            'ignored when --relax is passed.')
    minify_group.add_argument('-i', '--include', action='append',
        help='Additional ackages to include in the spec.  Can be passed '
            'multiple times:\n  ... -i pkg1 -i pkg2')
    minify_group.add_argument('-e', '--exclude', action='append', 
        help='Packages to exclude from the spec.  Can be passed multiple '
            'times:\n  ... -e pkg1 -e pkg2')
    minify_group.add_argument('--add_exclusion_deps', action='store_true',
        help='Whether to add dependencies of excluded packages to the '
            'minified spec.  E.g. using:n'
            '  ... --exclude pandas --add_exclusion_deps\n' 
            'removes pandas from the spec, but adds numpy, python_dateutil, '
            'and pytz - the next level of dependencies for pandas.')
    minify_group.add_argument('--add_builds', action='store_true', 
        help='Add the build number to the requirment. This is highly '
            'specific and will override loosening of version requirements.')

    relax_group = parser.add_argument_group(
        title=':==== Relax arguments ====',
        description='Options exclusively available when using RELAX (via '
            '--relax).  These are ignored unless --relax is passed.')
    relax_group.add_argument('-p', '--pin', action='append',
        help='Pins package version to full version. Packages not in the '
            'environment are ignored.  Can be passed multiple times:\n'
            '  ... -p numpy -p pandas\n')
    relax_group.add_argument('-o', '--override', action='append', nargs=2,
        help='Overrides the default `how` setting for any package. '
            'Takes 2 arguments, package name and new `how` method. Can be '
            'passed multiple times:\n'
            '  ... --how major -o pandas full -o numpy major')

    # if len(sys.argv) <= 1:
    #     parser.print_help(sys.stderr)
    #     sys.exit(1)

    args = parser.parse_args()
    # check for name and path characters in name
    if not args.name:
        args.path = os.path.dirname(sys.executable)
    elif ('/' in args.name) or ('\\' in args.name):
        args.path = args.name
    else:
        args.path = None

    cenv = CondaEnvironment(args.name, args.path)
    cenv.build_graph()

    if args.relax:
        yaml_str = cenv.relax_requirements(
            export_path=args.file,
            how=args.how,
            pin=args.pin,
            override=dict(args.override) if args.override else None
        )
    else:
        yaml_str = cenv.minify_requirements(
            export_path=args.file,
            include=args.include,
            exclude=args.exclude,
            add_exclusion_deps=args.add_exclusion_deps,
            how=args.how,
            add_builds=args.add_builds
        )

    if args.file:
        print('Minified environment specification written to '
            '"{}"'.format(args.file))
    else:
        print(yaml_str)
        
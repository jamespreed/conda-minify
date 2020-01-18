from .environment import CondaEnvironment

_epilog = """===>>> Example MINIFY usage <<<===
Export minified spec for myenv to the file path/to/env.yaml:
          [ conda-minify myenv minify ] -f path/to/env.yaml
Exclude pandas & matplotlib:      [...] -e pandas -e matplotlib
Loosen version to major release:  [...] --how major
Include Python, version to minor: [...] -i python --how minor

===>>> Example RELAX usage <<<===
Show all of myenv, but relax the requirments to the major release
           [ conda-minify myenv relax ] --how major
Relax to minor, pin two version:  [...] --how minor -p pandas -p numpy
Relax and override versions:      [...] -o pandas minor -o numpy minor
"""

def main():
    import sys
    import argparse
    import textwrap as _textwrap
    from argparse import RawTextHelpFormatter, ArgumentDefaultsHelpFormatter

    class MyHelpFormatter(RawTextHelpFormatter, ArgumentDefaultsHelpFormatter):
        def _split_lines(self, text, width):
            return [w for t in text.splitlines() 
                      for w in _textwrap.wrap(t, width)]

    parser = argparse.ArgumentParser(prog='conda-minify',
        description='Builds minimized Conda specs to share environments.',
        epilog=_epilog,
        formatter_class=MyHelpFormatter)
    parser.add_argument('name',
        help='The environment name to export. Use of a forward or backslash '
            'in the name converts the name to a path for the environment.')
    parser.add_argument('-f', '--file', default=None,
        help='The file path for export.  Leave off to print output to screen.')

    # create two method verbs that can be called
    subparsers = parser.add_subparsers(title='method (required)', 
        dest='method', 
        required=True,
        help='minify: exports the environment with the minimal package specs '
            'needed for a similar Codna environment.\nrelax: exports the '
            'entire environment spec with relaxed version numbers.')
    minify_parser = subparsers.add_parser('minify',
        formatter_class=MyHelpFormatter)
    relax_parser = subparsers.add_parser('relax', 
        formatter_class=MyHelpFormatter)    

    #######################
    # method: minify option
    minify_parser.add_argument('--how', default='full', 
        choices=['full', 'major', 'minor', 'none'],
        help='Controls how the version strings are added: \n'
            "- 'full' or 'true': Include the exact version.\n"
            "- 'major': Include major value only ('1.*').\n"  
            "- 'minor': Include major and minor ('1.11.*').\n" 
            "- 'none' or 'false': Version not added.\n")
    minify_parser.add_argument('-i', '--include', action='append',
        help='Additional ackages to include in the spec.  Can be passed '
            'multiple times:\n  ... -i pkg1 -i pkg2')
    minify_parser.add_argument('-e', '--exclude', action='append', 
        help='Packages to exclude from the spec.  Can be passed multiple '
            'times:\n  ... -e pkg1 -e pkg2')
    minify_parser.add_argument('--add_exclusion_deps', action='store_true',
        help='Whether to add dependencies of excluded packages to the '
            'minified spec.  E.g. using:n'
            '  ... --exclude pandas --add_exclusion_deps\n' 
            'removes pandas from the spec, but adds numpy, python_dateutil, '
            'and pytz - the next level of dependencies for pandas.')
    minify_parser.add_argument('--add_builds', action='store_true', 
        help='Add the build number to the requirment. This is highly '
            'specific and will override loosening of version requirements.')

    #######################
    # method: relax options
    relax_parser.add_argument('--how', default='minor',
        choices=['full', 'major', 'minor', 'none'],
        help="The default method for how requirements are relaxed.  Using "
            "the `pin` or `override` arguments takes precedence over this "
            "value.\n"
            "- 'full': Include the exact version\n"
            "- 'major': Include the major value only ('1.*')\n"
            "- 'minor': Include the major and minor ('1.11.*')\n"
            "- 'none': Version not added.)\n")
    relax_parser.add_argument('-p', '--pin', action='append',
        help='Sets which packages will have their full version pinned to the '
            'version in the environment.  Packages not in the environment are '
            'ignored.  Can be passed multiple times:\n'
            '  ... -p numpy -p pandas\n')
    relax_parser.add_argument('-o', '--override', action='append', nargs=2,
        help='Allows overriding the default `how` setting for any package. '
            'Takes 2 arguments, the package name the new `how` method. Can be '
            'passed multiple times:\n'
            '  ... --how major -o pandas full -o numpy major')

    if len(sys.argv) <= 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    # check for path characters in name
    if ('/' in args.name) or ('\\' in args.name):
        args.path = args.name
    else:
        args.path = None

    cenv = CondaEnvironment(args.name, args.path)
    cenv.build_graph()

    if args.method == 'minify':
        yaml_str = cenv.minify_requirements(
            export_path=args.file,
            include=args.include,
            exclude=args.exclude,
            add_exclusion_deps=args.add_exclusion_deps,
            how=args.how,
            add_builds=args.add_builds
        )
    if args.method == 'relax':
        yaml_str = cenv.relax_requirements(
            export_path=args.file,
            how=args.how,
            pin=args.pin,
            override=dict(args.override) if args.override else None
        )
    if args.file:
        print('Minified environment specification written to '
            '"{}"'.format(args.file))
    else:
        print(yaml_str)

if __name__ == '__main__':
    main()
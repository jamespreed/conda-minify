from .condadeps import CondaEnvironment


if __name__ == '__main__':
    import argparse
    from argparse import RawTextHelpFormatter, ArgumentDefaultsHelpFormatter
    import sys

    class MyHelpFormatter(RawTextHelpFormatter, ArgumentDefaultsHelpFormatter):
        pass

    parser = argparse.ArgumentParser(prog='CondaDeps',
        description='Maps dependencies in a Conda environment and builds '
            'minimized requirement specs to share environments.',
        formatter_class=MyHelpFormatter)

    # create two method verbs that can be called
    subparsers = parser.add_subparsers(title='methods', 
        help='minify: exports the environment with the minimal package specs '
            'needed for a similar Codna environment.\nrelax: exports the '
            'entire environment spec with relaxed version numbers.')
    minify_parser = subparsers.add_parser('minify', 
        formatter_class=MyHelpFormatter)
    relax_parser = subparsers.add_parser('relax', 
        formatter_class=MyHelpFormatter)
    # environment name is required
    parser.add_argument('name',
        help='The environment name to export. Use of a forward or backslash '
            'in the name converts the name to a path for the environment.')
    parser.add_argument('-f', '--file', default=None,
        help='The file path for export.')

    #######################
    # method: minify option
    minify_parser.add_argument('-i', '--include', action='append',
        help='Additional ackages to include in the spec.  Can be passed '
            'multiple times:\n  `... -i pkg1 -i pkg2`')
    minify_parser.add_argument('-e', '--exclude', action='append', 
        help='Packages to exclude from the spec.  Can be passed multiple '
            'times:\n  `... -e pkg1 -e pkg2`')
    minify_parser.add_argument('--add_versions', default='full', 
        choices=['full', 'major', 'minor', 'none', 'true', 'false'],
        help='Controls how the version strings are added: \n'
            "- 'full' or 'true': Include the exact version.\n"
            "- 'major': Include the major value of the version only ('1.*').\n"  
            "- 'minor': Include the major and minor versions ('1.11.*').\n" 
            "- 'none' or 'false': Version not added.\n")
    minify_parser.add_argument('--add_builds', action='store_true', 
        help='Add the build number to the requirment. This is highly '
            'specific and will override loosening of version requirements.')

    #######################
    # method: relax options
    relax_parser.add_argument('--how', default='minor',
        choices=['full', 'major', 'minor', 'none', 'true', 'false'],
        help="The default method for how requirements are relaxed.  Using "
            "the `pin` or `override` arguments takes precedence over this "
            "value.\n"
            "- 'full' or 'true': Include the exact version\n"
            "- 'major': Include the major value of the version only ('1.*')\n"
            "- 'minor': Include the major and minor versions ('1.11.*')\n"
            "- 'none' or 'false': Version not added.)\n")
    relax_parser.add_argument('-p', '--pin', action='append',
        help='Sets which packages will have their full version pinned to the '
            'version in the environment.  Packages not in the environment are '
            'ignored.  Can be passed multiple times:\n'
            '  `... -p numpy -p pandas`')
    relax_parser.add_argument('-o', '--override', action='append', nargs=2,
        help='Allows overriding the default `how` setting for any package. '
            'Takes 2 arguments, the package name the new `how` method. Can be '
            'passed multiple times:\n'
            '  `... -H major -o pandas full -o numpy major`')

    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    
    cenv = CondaEnvironment(args.name, args.path)
    cenv.build_graph()
    yaml_str = cenv.minify_requirements(
        export_path=args.file,
        include=args.include,
        exclude=args.exclude,
        add_versions=args.add_versions,
        add_builds=args.add_builds
    )
    if args.file:
        print('Minified environment specification written to '
            '"{}"'.format(args.file))
    else:
        print(yaml_str)
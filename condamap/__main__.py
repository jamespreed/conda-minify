from .condadeps import CondaEnvironment

if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog='CondaDeps',
        description='Maps dependencies in a Conda environment and builds '
                    'minimized requirement specs to share environments.'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-n', '--name',
        help='The environment name to export.')
    group.add_argument('-p', '--path',
        help='The environment path to export, use when exporting an '
           'environment that is not located in one of the directories show by '
           '`conda config --show envs_dirs`.')

    parser.add_argument('-f', '--file', default=None,
        help='The file path for export.')
    parser.add_argument('-i', '--include', action='append',
        help='Additional ackages to include in the spec.  Can be passed '
            'multiple times: `python condamap -n env -i pkg1 -i pkg2`')
    parser.add_argument('-e', '--exclude', action='append', 
        help='Packages to exclude from the spec.  Can be passed multiple '
            'times: `python condamap -n env -e pkg1 -e pkg2`')
    parser.add_argument('--add_versions', default='full', 
        choices=['full', 'major', 'minor', 'none', 'true', 'false'],
        help="""Controls how the version strings are added: 
            'full' or 'true' - Include the exact version.  
            'major' - Include the major value of the version only ('1.*').  
            'minor' - Include the major and minor versions ('1.11.*').  
            'none' or 'false' - Version not added.""")
    parser.add_argument('--add_builds', action='store_true', 
        help='Add the build number to the requirment. This is highly '
            'specific and will override loosening of version requirements.')

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
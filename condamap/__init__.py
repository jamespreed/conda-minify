if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        prog='CondaDeps',
        description='Maps dependencies in a Conda environment and builds '
                    'minimized requirement specs to share environments.'
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-n', '--name',
        help='The environment name to export.  Defaults to "base" if neither '
        '-n/--name nor -p/--path are given.')
    group.add_argument('-p', '--path',
        help='The environment path to export, use when exporting an '
           'environment that is not located in one of the directories show by '
           '`conda config --show envs_dirs`.')

    args = parser.parse_args()
    if not args.name and not args.path:
        args.name = 'base'

    
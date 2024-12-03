"""
OPERA-DISP Tile Map Service Generator
"""

import argparse
import os
import sys
from importlib.metadata import entry_points

from hyp3lib.fetch import write_credentials_to_netrc_file


def main():
    """Main entrypoint for HyP3 processing

    Calls the HyP3 entrypoint specified by the `++process` argument
    """
    parser = argparse.ArgumentParser(prefix_chars='+', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '++process',
        choices=['generate_opera_disp_tile'],
        default='generate_opera_disp_tile',
        help='Select the HyP3 entrypoint to use',  # HyP3 entrypoints are specified in `pyproject.toml`
    )
    args, unknowns = parser.parse_known_args()

    username = os.getenv('EARTHDATA_USERNAME')
    password = os.getenv('EARTHDATA_PASSWORD')
    if username and password:
        write_credentials_to_netrc_file(username, password, append=False)

    # NOTE: Cast to set because of: https://github.com/pypa/setuptools/issues/3649
    (process_entry_point,) = set(entry_points(group='hyp3', name=args.process))
    sys.argv = [args.process, *unknowns]
    sys.exit(process_entry_point.load()())


if __name__ == '__main__':
    main()

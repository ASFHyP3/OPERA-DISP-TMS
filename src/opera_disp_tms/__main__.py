"""OPERA-DISP Tile Map Service Generator"""

import argparse
import sys
from importlib.metadata import entry_points


def main():
    """Main entrypoint for HyP3 processing

    Calls the HyP3 entrypoint specified by the `++process` argument
    """
    parser = argparse.ArgumentParser(prefix_chars='+', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '++process',
        choices=['create_measurement_geotiff', 'create_tile_map'],
        default='create_measurement_geotiff',
        help='Select the HyP3 entrypoint to use',  # HyP3 entrypoints are specified in `pyproject.toml`
    )

    args, unknowns = parser.parse_known_args()
    process_entry_point = list(entry_points(group='hyp3', name=args.process))[0]

    sys.argv = [args.process, *unknowns]
    sys.exit(process_entry_point.load()())


if __name__ == '__main__':
    main()

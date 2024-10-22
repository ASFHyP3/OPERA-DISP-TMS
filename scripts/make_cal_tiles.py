import argparse
from datetime import datetime
from pathlib import Path

from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.generate_sw_disp_tile import create_sw_disp_tile
from opera_disp_tms.generate_sw_vel_tile import create_sw_vel_tile
from opera_disp_tms.utils import create_tile_name


def make_cal_tiles(meta_tile_dir: Path, workflow: str, begin_date: datetime, end_date: datetime):
    workflow_opts = {
        'displacement': ['SW_CUMUL_DISP', create_sw_disp_tile, None],
        'velocity': ['SW_VELOCITY', create_sw_vel_tile, [-0.05, 0.05]],
    }
    prod_type, create_tile_func, scale_range = workflow_opts[workflow]
    tiles = list(meta_tile_dir.glob('*.tif'))
    for tile in tiles:
        product_name = Path(create_tile_name(tile.name, begin_date, end_date, prod_type))
        if product_name.exists():
            print(f'{product_name} already exists. Skipping.')
            continue
        create_tile_func(tile, begin_date, end_date)

    tiles = [str(x) for x in Path.cwd().glob('*.tif')]
    tileset_dir = Path.cwd() / 'tiles'
    tileset_dir.mkdir(exist_ok=True)

    create_tile_map(str(tileset_dir), tiles, scale_range)


def main():
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('meta_tile_dir', type=str, help='Path to the metadata tile')
    parser.add_argument(
        'workflow', type=str, choices=['displacement', 'velocity'], help='Workflow to run (displacement or velocity)'
    )
    parser.add_argument(
        '--begin-date',
        type=str,
        default='20170101',
        help='Start of secondary date search range to generate tile for (e.g., 20240101)',
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default='20171231',
        help='End of secondary date search range to generate tile for (e.g., 20240101)',
    )

    args = parser.parse_args()
    args.meta_tile_dir = Path(args.meta_tile_dir)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')
    make_cal_tiles(args.meta_tile_dir, args.workflow, args.begin_date, args.end_date)


if __name__ == '__main__':
    main()

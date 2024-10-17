import argparse
from datetime import datetime
from pathlib import Path

from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.generate_sw_disp_tile import create_product_name, create_sw_disp_tile


def make_cal_sw_disp_tiles(meta_tile_dir: Path, begin_date: datetime, end_date: datetime):
    tiles = list(meta_tile_dir.glob('*.tif'))
    for tile in tiles:
        product_name = Path(create_product_name(tile.name, begin_date, end_date))
        if product_name.exists():
            print(f'{product_name} already exists. Skipping.')
            continue
        create_sw_disp_tile(tile, begin_date, end_date)

    sw_disp_tiles = [str(x) for x in Path.cwd().glob('*.tif')]
    tileset_dir = Path.cwd() / 'tiles'
    tileset_dir.mkdir(exist_ok=True)
    create_tile_map(str(tileset_dir), sw_disp_tiles)


def main():
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('meta_tile_dir', type=str, help='Path to the metadata tile')
    parser.add_argument(
        '--begin_date',
        type=str,
        default='20170101',
        help='Start of secondary date search range to generate tile for (e.g., 20240101)',
    )
    parser.add_argument(
        '--end_date',
        type=str,
        default='20171231',
        help='End of secondary date search range to generate tile for (e.g., 20240101',
    )

    args = parser.parse_args()
    args.meta_tile_dir = Path(args.meta_tile_dir)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')
    make_cal_sw_disp_tiles(args.meta_tile_dir, args.begin_date, args.end_date)


if __name__ == '__main__':
    main()

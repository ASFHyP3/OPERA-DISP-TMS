import argparse
from pathlib import Path

from opera_disp_tms.generate_metadata_tile import create_product_name, create_tile_for_bbox


def make_cal_meta_tiles(orbit_direction):
    script_dir = Path(__file__).parent
    with open(script_dir / 'cal_corners.txt', 'r') as f:
        corners = [[int(val) for val in corner.strip().split(' ')] for corner in f.readlines()]

    for corner in corners:
        bbox = [corner[0], corner[1] - 1, corner[0] + 1, corner[1]]
        product_name = Path(create_product_name(['metadata'], orbit_direction, bbox) + '.tif')
        if product_name.exists():
            print(f'{product_name} already exists. Skipping.')
            continue
        create_tile_for_bbox(bbox, orbit_direction)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('orbit_direction', choices=['ascending', 'descending'])
    args = parser.parse_args()
    make_cal_meta_tiles(args.orbit_direction)


if __name__ == '__main__':
    main()

import argparse
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Iterable

from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.generate_metadata_tile import create_tile_for_bbox
from opera_disp_tms.generate_sw_disp_tile import create_sw_disp_tile
from opera_disp_tms.generate_sw_vel_tile import create_sw_vel_tile
from opera_disp_tms.tmp_s3_access import get_temporary_s3_session
from opera_disp_tms.utils import upload_dir_to_s3


def generate_opera_disp_tile(
    tile_type: str, corner: Iterable[int], direction: str, begin_date: datetime, end_date: datetime
):
    s3_client = get_temporary_s3_session()
    bbox = [corner[0], corner[1] - 1, corner[0] + 1, corner[1]]
    metadata_path = create_tile_for_bbox(bbox, direction=direction)
    if not metadata_path:
        return

    if tile_type == 'displacement':
        out_path = create_sw_disp_tile(metadata_path, begin_date, end_date)
    elif tile_type == 'secant_velocity':
        out_path = create_sw_vel_tile(metadata_path, begin_date, end_date, minmax=True)
    elif tile_type == 'velocity':
        out_path = create_sw_vel_tile(metadata_path, begin_date, end_date, minmax=False)
    else:
        raise ValueError(f'Unsupported tile type: {tile_type}')

    return out_path


def generate_opera_disp_tiles(
    tile_type: str, bbox: Iterable[int], direction: str, begin_date: datetime, end_date: datetime
):
    tiles = []
    for corner in product(range(bbox[0], bbox[2]), range(bbox[1], bbox[3])):
        tiles.append(generate_opera_disp_tile(tile_type, corner, direction, begin_date, end_date))

    scale = {
        'displacement': None,
        'seacant_velocity': [-0.05, 0.05],
        'velocity': [-0.05, 0.05],
    }
    create_tile_map(tile_type, [str(x) for x in tiles], scale[tile_type])
    return Path(tile_type)


def main():
    """CLI entrypoint"""
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('--bucket', help='AWS S3 bucket HyP3 for upload the final products')
    parser.add_argument('--bucket-prefix', default='', help='Add a bucket prefix to products')
    parser.add_argument(
        'tile_type', type=str, choices=['displacement', 'secant_velocity', 'velocity'], help='Type of tile to produce'
    )
    parser.add_argument('bbox', type=int, nargs=4, help='Upper left corner of tile in form: min_lon max_lat')
    parser.add_argument('direction', type=str, choices=['ascending', 'descending'], help='Direction of the orbit pass')
    parser.add_argument(
        'begin_date', type=str, help='Start of secondary date search range to generate tile for (e.g., 20211231)'
    )
    parser.add_argument(
        'end_date', type=str, help='End of secondary date search range to generate tile for (e.g., 20211231)'
    )

    args = parser.parse_args()
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    opera_disp_tiles = generate_opera_disp_tiles(
        args.tile_type, args.bbox, args.direction, args.begin_date, args.end_date
    )
    if args.bucket:
        upload_dir_to_s3(opera_disp_tiles, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

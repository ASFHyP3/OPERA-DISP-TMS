import argparse
from datetime import datetime
from itertools import product
from pathlib import Path

from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.generate_metadata_tile import create_tile_for_bbox
from opera_disp_tms.generate_sw_disp_tile import create_sw_disp_tile
from opera_disp_tms.generate_sw_vel_tile import create_sw_vel_tile
from opera_disp_tms.utils import upload_dir_to_s3


def divide_bbox_into_tiles(bbox: list[int]) -> list[list[int]]:
    tiles = []
    for lon in range(bbox[0], bbox[2]):
        for lat in range(bbox[1], bbox[3]):
            tiles.append([lon, lat, lon + 1, lat + 1])
    return tiles


def generate_opera_disp_tile(
    tile_type: str, bbox: list[int], direction: str, begin_date: datetime, end_date: datetime
):
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
    tile_type: str, bbox: list[int], direction: str, begin_date: datetime, end_date: datetime
):
    tiles = []
    for tile_bbox in divide_bbox_into_tiles(bbox):
        tiles.append(generate_opera_disp_tile(tile_type, tile_bbox, direction, begin_date, end_date))

    scale = {
        'displacement': None,
        'secant_velocity': [-0.05, 0.05],
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
    parser.add_argument(
        'bbox',
        type=str.split,
        nargs='+',
        help='Integer bounds in EPSG:4326, formatted like [min lon, min lat, max lon, max lat]'
    )
    parser.add_argument('direction', type=str, choices=['ascending', 'descending'], help='Direction of the orbit pass')
    parser.add_argument(
        'begin_date', type=str, help='Start of secondary date search range to generate tile for (e.g., 20211231)'
    )
    parser.add_argument(
        'end_date', type=str, help='End of secondary date search range to generate tile for (e.g., 20211231)'
    )

    args = parser.parse_args()

    args.bbox = [int(item) for sublist in args.bbox for item in sublist]
    if len(args.bbox) != 4:
        parser.error('Bounds must have exactly 4 values: [min lon, min lat, max lon, max lat] in EPSG:4326.')

    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    opera_disp_tiles = generate_opera_disp_tiles(
        args.tile_type, args.bbox, args.direction, args.begin_date, args.end_date
    )
    if args.bucket:
        upload_dir_to_s3(opera_disp_tiles, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

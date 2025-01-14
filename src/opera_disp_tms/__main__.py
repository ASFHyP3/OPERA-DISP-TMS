"""OPERA-DISP Tile Map Service Generator"""

import argparse
from datetime import datetime
from pathlib import Path

from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.generate_metadata_tile import create_tile_for_bbox
from opera_disp_tms.generate_sw_disp_tile import create_sw_disp_tile
from opera_disp_tms.generate_sw_vel_tile import create_sw_vel_tile
from opera_disp_tms.utils import partition_bbox, upload_dir_to_s3


class Date(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            value = datetime.strptime(values, '%Y%m%d')
        except ValueError:
            parser.error(f'{self.dest} must be formatted YYYYMMDD, e.g. 20211231')
        setattr(namespace, self.dest, value)


class Frames(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            frames = [int(item) for sublist in values for item in sublist]
        except ValueError:
            parser.error(f'{self.dest} values must be integers between 0 and TBD')
        for frame in frames:
            if not (0 <= frame <= 99999): # FIXME find actual max
                parser.error(f'{self.dest} value {frame} must be between 0 and 99999')
        setattr(namespace, self.dest, frames)


def generate_mosaic_geotiff(
    tile_type: str, frame: int, begin_date: datetime, end_date: datetime
) -> Path:
    if tile_type == 'displacement':
        mosaic_geotiff = create_sw_disp_tile(frame, begin_date, end_date)
    elif tile_type == 'secant_velocity':
        mosaic_geotiff = create_sw_vel_tile(frame, begin_date, end_date, secant=True)
    else:
        raise ValueError(f'Unsupported tile type: {tile_type}')

    return mosaic_geotiff


def generate_tile_map_service(
    tile_type: str, frames: list[int], direction: str, begin_date: datetime, end_date: datetime
) -> Path:
    mosaic_geotiffs = []
    for frame in frames:
        print(f'Processing frame {frame}')
        mosaic_geotiff = generate_mosaic_geotiff(tile_type, frame, direction, begin_date, end_date)
        mosaic_geotiffs.append(mosaic_geotiff.name)

    scale = {
        'displacement': None,
        'secant_velocity': [-0.05, 0.05],
    }
    create_tile_map(tile_type, mosaic_geotiffs, scale[tile_type])
    return Path(tile_type)


def main():
    """HyP3 CLI entrypoint to create a Tile Map Service (TMS) visualization of the OPERA Displacement data set"""
    parser = argparse.ArgumentParser(
        description='Create a Tile Map Service (TMS) visualization of the OPERA Displacement data set'
    )
    parser.add_argument('--bucket', help='AWS S3 bucket HyP3 for upload the final products')
    parser.add_argument('--bucket-prefix', default='', help='Add a bucket prefix to products')
    parser.add_argument(
        'tile_type', type=str, choices=['displacement', 'secant_velocity'], help='Data value to visualize'
    )
    parser.add_argument(
        'frames',
        type=str.split,
        nargs='+',
        action=Frames,
        help='List of frame ids to include in mosaic',
    )
    parser.add_argument('direction', type=str, choices=['ascending', 'descending'], help='Direction of the orbit pass')
    parser.add_argument(
        'begin_date', type=str, action=Date, help='Start of secondary date search range to visualize (e.g., 20211231)'
    )
    parser.add_argument(
        'end_date', type=str, action=Date, help='End of secondary date search range to visualize (e.g., 20211231)'
    )
    args = parser.parse_args()

    output_directory = generate_tile_map_service(
        args.tile_type, args.frames, args.direction, args.begin_date, args.end_date
    )
    if args.bucket:
        upload_dir_to_s3(output_directory, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

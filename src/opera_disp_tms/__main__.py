"""OPERA-DISP Tile Map Service Generator"""

import argparse
from datetime import datetime
from pathlib import Path

from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.generate_metadata_tile import create_tile_for_bbox
from opera_disp_tms.generate_sw_disp_tile import create_sw_disp_tile
from opera_disp_tms.generate_sw_vel_tile import create_sw_vel_tile
from opera_disp_tms.utils import upload_dir_to_s3


class Date(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            value = datetime.strptime(values, '%Y%m%d')
        except ValueError:
            parser.error(f'{self.dest} must be formatted YYYYMMDD, e.g. 20211231')
        setattr(namespace, self.dest, value)


class Bbox(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            bbox = tuple(int(item) for sublist in values for item in sublist)
        except ValueError:
            parser.error(f'{self.dest} values must be integers ordered [min lon, min lat, max lon, max lat]')
        if len(bbox) != 4:
            parser.error(f'{self.dest} must have exactly 4 values ordered [min lon, min lat, max lon, max lat]')
        if not (-180 <= bbox[0] <= bbox[2] <= 180 and -90 <= bbox[1] <= bbox[3] <= 90):
            parser.error(f'{self.dest} must be ordered [min lon, min lat, max lon, max lat]')
        setattr(namespace, self.dest, bbox)


def generate_mosaic_geotiff(
    tile_type: str, bbox: tuple[int, int, int, int], direction: str, begin_date: datetime, end_date: datetime
) -> Path:
    metadata_geotiff = create_tile_for_bbox(bbox, direction=direction)
    if not metadata_geotiff:
        raise ValueError(f'No data found for bounding box {bbox} and direction {direction}')

    if tile_type == 'displacement':
        mosaic_geotiff = create_sw_disp_tile(metadata_geotiff, begin_date, end_date)
    elif tile_type == 'secant_velocity':
        mosaic_geotiff = create_sw_vel_tile(metadata_geotiff, begin_date, end_date, minmax=True)
    else:
        raise ValueError(f'Unsupported tile type: {tile_type}')

    return mosaic_geotiff


def generate_tile_map_service(
    tile_type: str, bbox: tuple[int, int, int, int], direction: str, begin_date: datetime, end_date: datetime
) -> Path:
    mosaic = generate_mosaic_geotiff(tile_type, bbox, direction, begin_date, end_date)

    scale = {
        'displacement': None,
        'secant_velocity': [-0.05, 0.05],
    }
    create_tile_map(tile_type, [mosaic], scale[tile_type])
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
        'bbox',
        type=str.split,
        nargs='+',
        action=Bbox,
        help='Integer bounds in EPSG:4326, formatted like [min lon, min lat, max lon, max lat]',
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
        args.tile_type, args.bbox, args.direction, args.begin_date, args.end_date
    )
    if args.bucket:
        upload_dir_to_s3(output_directory, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

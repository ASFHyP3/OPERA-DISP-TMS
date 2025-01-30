"""OPERA-DISP Tile Map Service Generator"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from osgeo import gdal

from opera_disp_tms.create_measurement_geotiff import create_measurement_geotiff
from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.utils import upload_dir_to_s3


gdal.UseExceptions()


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
            parser.error(f'{self.dest} values must be integers between 1 and 46986')
        for frame in frames:
            if not (1 <= frame <= 46986):
                parser.error(f'{self.dest} value {frame} must be between 1 and 46986')
        setattr(namespace, self.dest, frames)


def get_west_most_point(geotiff_path: str) -> float:
    info = gdal.Info(geotiff_path, format='json')
    west_most = min(coord[0] for coord in info['wgs84Extent']['coordinates'][0])
    return west_most


def get_frame_id(geotiff_path: str) -> int:
    info = gdal.Info(geotiff_path, format='json')
    return int(info['metadata']['']['frame_id'])


def get_common_direction(frame_ids: set[int]):
    data_file = Path(__file__).parent / 'data' / 'frame_directions.json'
    frame_directions = json.loads(data_file.read_text())
    for direction, frame_list in frame_directions.items():
        if frame_ids <= set(frame_list):
            return direction
    raise ValueError('Frames do not share a common flight direction')


def generate_tile_map_service(
    measurement_type: str, frames: list[int], begin_date: datetime, end_date: datetime
) -> Path:
    measurement_geotiffs = []
    for frame in frames:
        print(f'Processing frame {frame}')
        measurement_geotiff = create_measurement_geotiff(measurement_type, frame, begin_date, end_date)
        measurement_geotiffs.append(measurement_geotiff.name)

    frame_ids = {get_frame_id(geotiff) for geotiff in measurement_geotiffs}
    direction = get_common_direction(frame_ids)
    measurement_geotiffs.sort(key=lambda x: get_west_most_point(x), reverse=direction == 'DESCENDING')

    scale = {
        'displacement': None,
        'secant_velocity': [-0.05, 0.05],
        'velocity': [-0.05, 0.05],
    }
    create_tile_map(measurement_type, measurement_geotiffs, scale[measurement_type])
    return Path(measurement_type)


def main():
    """HyP3 CLI entrypoint to create a Tile Map Service (TMS) visualization of the OPERA Displacement data set"""
    parser = argparse.ArgumentParser(
        description='Create a Tile Map Service (TMS) visualization of the OPERA Displacement data set'
    )
    parser.add_argument('--bucket', help='AWS S3 bucket HyP3 for upload the final products')
    parser.add_argument('--bucket-prefix', default='', help='Add a bucket prefix to products')
    parser.add_argument(
        'measurement_type',
        type=str,
        choices=['displacement', 'secant_velocity', 'velocity'],
        help='Data measurement to visualize',
    )
    parser.add_argument(
        'frames', type=str.split, nargs='+', action=Frames, help='List of frame ids to include in mosaic'
    )
    parser.add_argument(
        'begin_date', type=str, action=Date, help='Start of secondary date search range to visualize (e.g., 20211231)'
    )
    parser.add_argument(
        'end_date', type=str, action=Date, help='End of secondary date search range to visualize (e.g., 20211231)'
    )
    args = parser.parse_args()

    output_directory = generate_tile_map_service(args.measurement_type, args.frames, args.begin_date, args.end_date)
    if args.bucket:
        upload_dir_to_s3(output_directory, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

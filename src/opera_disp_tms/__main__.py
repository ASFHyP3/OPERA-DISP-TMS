"""
OPERA-DISP Tile Map Service Generator
"""

import argparse
import datetime
import os

from hyp3lib.fetch import write_credentials_to_netrc_file

from opera_disp_tms.generate_opera_disp_tile import generate_opera_disp_tiles
from opera_disp_tms.utils import upload_dir_to_s3


def main():
    """CLI entrypoint"""
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('--bucket', help='AWS S3 bucket HyP3 for upload the final products')
    parser.add_argument('--bucket-prefix', default='', help='Add a bucket prefix to products')
    parser.add_argument(
        'tile_type', type=str, choices=['displacement', 'secant_velocity'], help='Type of tile to produce'
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

    username = os.getenv('EARTHDATA_USERNAME')
    password = os.getenv('EARTHDATA_PASSWORD')
    if username and password:
        write_credentials_to_netrc_file(username, password, domain='uat.urs.earthdata.nasa.gov', append=False)

    opera_disp_tiles = generate_opera_disp_tiles(
        args.tile_type, args.bbox, args.direction, args.begin_date, args.end_date
    )
    if args.bucket:
        upload_dir_to_s3(opera_disp_tiles, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

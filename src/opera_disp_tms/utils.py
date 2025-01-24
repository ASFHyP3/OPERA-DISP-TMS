import os
from datetime import datetime, timedelta
from mimetypes import guess_type
from pathlib import Path
from typing import Union

import boto3
import requests
from osgeo import gdal


gdal.UseExceptions()

S3_CLIENT = boto3.client('s3')
DATE_FORMAT = '%Y%m%dT%H%M%SZ'


def download_file(
    url: str,
    download_path: Union[Path, str] = '.',
    chunk_size=10 * (2**20),
) -> None:
    """Download a file without authentication.

    Args:
        url: URL of the file to download
        download_path: Path to save the downloaded file to
        chunk_size: Size to chunk the download into
    """
    session = requests.Session()

    with session.get(url, stream=True) as s:
        s.raise_for_status()
        with open(download_path, 'wb') as f:
            for chunk in s.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    session.close()


def within_one_day(date1: datetime, date2: datetime) -> bool:
    """Check if two dates are within one day of each other"""
    return abs(date1 - date2) <= timedelta(days=1)


def create_tile_name(
    frame_id: int, begin_date: datetime, end_date: datetime, prod_type: str = 'SW_CUMUL_DISP'
) -> str:
    """Create a product name for a short wavelength cumulative displacement tile
    Takes the form: SW_CUMUL_DISP_YYYYMMDD_YYYYMMDD_DIRECTION_TILECOORDS.tif

    Args:
        metadata_name: The name of the metadata file
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for
        prod_type: Product type prefix to use
    """
    date_fmt = '%Y%m%d'
    begin_date_str = datetime.strftime(begin_date, date_fmt)
    end_date_str = datetime.strftime(end_date, date_fmt)
    name = f'{frame_id}_{prod_type}_{begin_date_str}_{end_date_str}.tif'
    return name


def upload_file_to_s3(path_to_file: Path, bucket: str, key):
    extra_args = {'ContentType': guess_type(path_to_file)[0]}
    S3_CLIENT.upload_file(str(path_to_file), bucket, key, ExtraArgs=extra_args)

    # tag files as 'product' so hyp3 doesn't treat the .png files as browse images
    tag_set = {'TagSet': [{'Key': 'file_type', 'Value': 'product'}]}
    S3_CLIENT.put_object_tagging(Bucket=bucket, Key=key, Tagging=tag_set)


def upload_dir_to_s3(path_to_dir: Path, bucket: str, prefix: str = ''):
    """Upload a local directory, subdirectory, and all contents to an S3 bucket

    Args:
        path_to_dir: The local path to directory
        bucket: S3 bucket to which the directory should be uploaded
        prefix: prefix in S3 bucket to upload the directory to. Defaults to ''
    """
    for branch in os.walk(path_to_dir, topdown=True):
        for filename in branch[2]:
            path_to_file = Path(branch[0]) / filename
            key = str(prefix / path_to_file.relative_to(path_to_dir))
            upload_file_to_s3(path_to_file, bucket, key)

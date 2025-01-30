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


def list_files_in_s3(bucket: str, bucket_prefix: str):
    resp = S3_CLIENT.list_objects_v2(Bucket=bucket, Prefix=bucket_prefix)

    return resp['Contents']


def download_file_from_s3(bucket: str, download_key, dest_dir: Path) -> Path:
    """Download a file from an S3 bucket

    Args:
        uri: URI of the file to download
        dest_dir: the directory to place the downloaded file in
    """
    filename, output_path = make_output_path(dest_dir, download_key)

    S3_CLIENT.download_file(bucket, download_key, output_path)

    return output_path


def make_output_path(dest_dir: Path, download_key: str):
    filename = Path(download_key).parts[-1]

    output_path = dest_dir / filename

    return output_path, filename


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

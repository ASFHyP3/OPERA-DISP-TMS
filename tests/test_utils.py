from datetime import datetime
from pathlib import Path
from unittest.mock import call, patch

import pytest
from botocore.stub import ANY, Stubber
from moto import mock_aws
from moto.core import patch_client

import opera_disp_tms.utils as ut


@pytest.fixture(autouse=False)
def s3_stubber():
    with Stubber(ut.S3_CLIENT) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


def test_within_in_day():
    assert ut.within_one_day(datetime(2021, 1, 1, 12, 1, 1), datetime(2021, 1, 2, 0, 0, 0))
    assert not ut.within_one_day(datetime(2021, 1, 1, 12, 1, 1), datetime(2021, 1, 2, 12, 1, 2))


def test_upload_file_to_s3(tmp_path, s3_stubber):
    expected_params = {
        'Body': ANY,
        'Bucket': 'myBucket',
        'Key': 'myPrefix/myObject.png',
        'ContentType': 'image/png',
        'ChecksumAlgorithm': 'CRC32',
    }
    tag_params = {
        'Bucket': 'myBucket',
        'Key': 'myPrefix/myObject.png',
        'Tagging': {'TagSet': [{'Key': 'file_type', 'Value': 'product'}]},
    }
    s3_stubber.add_response(method='put_object', expected_params=expected_params, service_response={})
    s3_stubber.add_response(method='put_object_tagging', expected_params=tag_params, service_response={})

    file_to_upload = tmp_path / 'myFile.png'
    file_to_upload.touch()
    ut.upload_file_to_s3(file_to_upload, 'myBucket', key='myPrefix/myObject.png')


def test_upload_dir_to_s3(tmp_path):
    files_to_upload = [
        tmp_path / 'subdir1' / 'subdir2' / 'foo.txt',
        tmp_path / 'subdir1' / 'subdir3' / 'bar.txt',
    ]
    for file_to_upload in files_to_upload:
        Path(file_to_upload).parent.mkdir(parents=True, exist_ok=True)
        file_to_upload.touch()

    with patch.object(ut, 'upload_file_to_s3') as mock_upload:
        ut.upload_dir_to_s3(tmp_path, 'myBucket', 'myPrefix')
        mock_upload.assert_has_calls(
            [
                call(tmp_path / 'subdir1/subdir2/foo.txt', 'myBucket', 'myPrefix/subdir1/subdir2/foo.txt'),
                call(tmp_path / 'subdir1/subdir3/bar.txt', 'myBucket', 'myPrefix/subdir1/subdir3/bar.txt'),
            ]
        )


@mock_aws
def test_list_files_in_s3(s3_bucket):
    prefix = 'geotiffs'
    geotiffs = [
        f'{prefix}/my-file1.tif',
        f'{prefix}/my-file2.tif',
        f'{prefix}/my-file3.tif',
    ]

    for tif in geotiffs:
        ut.S3_CLIENT.put_object(Bucket=s3_bucket, Key=tif)

    files = ut.list_files_in_s3(s3_bucket, prefix)

    assert len(files) == len(geotiffs)
    assert files[0]['Key'].endswith('.tif')


@mock_aws
def test_download_file_from_s3(tmp_path, s3_bucket):
    download_path = 'geotiffs/my-file.tif'
    dest_dir = Path(tmp_path)

    ut.S3_CLIENT.put_object(Bucket=s3_bucket, Key=download_path)

    output_path = ut.download_file_from_s3(s3_bucket, download_path, dest_dir)

    assert output_path == tmp_path / 'my-file.tif'


@pytest.fixture
def s3_bucket(scope='function'):
    with mock_aws():
        patch_client(ut.S3_CLIENT)

        bucketName = 'myBucket'
        location = {'LocationConstraint': 'us-west-2'}

        ut.S3_CLIENT.create_bucket(Bucket=bucketName, CreateBucketConfiguration=location)

        yield bucketName

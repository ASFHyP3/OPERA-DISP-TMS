from datetime import datetime
from pathlib import Path
from unittest.mock import call, patch

import pytest
from botocore.stub import ANY, Stubber

import opera_disp_tms.utils as ut


@pytest.fixture(autouse=True)
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

        
def test_list_files_in_s3(s3_stubber, list_objects_response):
    s3_stubber.add_response('list_objects_v2', list_objects_response)

    files = ut.list_files_in_s3('myBucket', 'myPrefix')

    assert len(files) == len(list_objects_response['Contents'])
    assert files[0]['Key'].endswith('.tif')


def test_make_output_path(tmp_path, s3_stubber):
    download_path = 'geotiffs/my-file.tif'
    dest_dir = tmp_path

    output_path, filename = ut.make_output_path(dest_dir, download_path)

    assert output_path == tmp_path / 'my-file.tif'
    assert filename == 'my-file.tif'


@pytest.fixture
def list_objects_response():
    return {
        'Contents': [
            {
                'Key': 'disp-geotiffs/displacement_11113_20140101_20260101.tif',
                'LastModified': datetime(2025, 1, 1),
                'ETag': '"4a25e8a5fb5b0a7d02b0b25b137e2a21-2"',
                'Size': 275547567,
                'StorageClass': 'STANDARD',
            },
            {
                'Key': 'disp-geotiffs/displacement_11114_20140101_20260101.tif',
                'LastModified': datetime(2025, 1, 1),
                'ETag': '"e8036c00b4433ee9df9f1d7ed33671e4-2"',
                'Size': 275328187,
                'StorageClass': 'STANDARD',
            },
            {
                'Key': 'disp-geotiffs/displacement_11115_20140101_20260101.tif',
                'LastModified': datetime(2025, 1, 1),
                'ETag': '"633fa5c46a45569b16b11dc27e736c88-2"',
                'Size': 275147777,
                'StorageClass': 'STANDARD',
            },
        ]
    }
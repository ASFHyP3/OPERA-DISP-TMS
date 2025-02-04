from datetime import datetime
from pathlib import Path
from unittest.mock import call, patch

import pytest
from moto import mock_aws
from moto.core import patch_client

import opera_disp_tms.utils as ut


def test_within_in_day():
    assert ut.within_one_day(datetime(2021, 1, 1, 12, 1, 1), datetime(2021, 1, 2, 0, 0, 0))
    assert not ut.within_one_day(datetime(2021, 1, 1, 12, 1, 1), datetime(2021, 1, 2, 12, 1, 2))


@mock_aws
def test_upload_file_to_s3(tmp_path, s3_bucket):
    file_to_upload = tmp_path / 'myFile.png'
    file_to_upload.touch()

    ut.upload_file_to_s3(file_to_upload, s3_bucket, key='myPrefix/myObject.png')

    resp = ut.S3_CLIENT.get_object(Bucket=s3_bucket, Key='myPrefix/myObject.png')

    assert resp['ContentType'] == 'image/png'

    tag_resp = ut.S3_CLIENT.get_object_tagging(Bucket=s3_bucket, Key='myPrefix/myObject.png')

    assert len(tag_resp['TagSet']) == 1
    tag = tag_resp['TagSet'].pop()

    assert tag['Key'] == 'file_type'
    assert tag['Value'] == 'product'


@mock_aws
def test_upload_dir_to_s3(tmp_path, s3_bucket):
    files_to_upload = [
        tmp_path / 'subdir1' / 'subdir2' / 'foo.txt',
        tmp_path / 'subdir1' / 'subdir3' / 'bar.txt',
    ]

    for file_to_upload in files_to_upload:
        Path(file_to_upload).parent.mkdir(parents=True, exist_ok=True)
        file_to_upload.touch()

    ut.upload_dir_to_s3(tmp_path, s3_bucket, 'myPrefix')

    resp = ut.S3_CLIENT.list_objects_v2(Bucket=s3_bucket, Prefix='myPrefix')

    assert len(resp['Contents']) == 2
    assert resp['Contents'][0]['Key'] == 'myPrefix/subdir1/subdir2/foo.txt'
    assert resp['Contents'][1]['Key'] == 'myPrefix/subdir1/subdir3/bar.txt'



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

    assert len(files) == 3
    assert files[0]['Key'] == f'{prefix}/my-file1.tif'
    assert files[1]['Key'] == f'{prefix}/my-file2.tif'
    assert files[2]['Key'] == f'{prefix}/my-file3.tif'


@mock_aws
def test_download_file_from_s3(tmp_path, s3_bucket):
    object_key = 'geotiffs/my-file.tif'

    ut.S3_CLIENT.put_object(Bucket=s3_bucket, Key=object_key)

    output_path = ut.download_file_from_s3(s3_bucket, object_key, tmp_path)

    assert output_path == tmp_path / 'my-file.tif'
    assert output_path.exists()


@pytest.fixture
def s3_bucket():
    with mock_aws():
        patch_client(ut.S3_CLIENT)

        bucket_name = 'myBucket'
        location = {'LocationConstraint': 'us-west-2'}

        ut.S3_CLIENT.create_bucket(Bucket=bucket_name, CreateBucketConfiguration=location)

        yield bucket_name


def test_get_frame_id():
    info = {
        'metadata': {
            '': {
                'frame_id': '11113',
            },
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert ut.get_frame_id('foo.tiff') == 11113
        mock_info.assert_called_once_with('foo.tiff', format='json')

    info = {
        'metadata': {
            '': {
                'frame_id': '321',
            },
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert ut.get_frame_id('bar.tiff') == 321
        mock_info.assert_called_once_with('bar.tiff', format='json')


def test_get_west_most_point():
    info = {
        'wgs84Extent': {
            'type': 'Polygon',
            'coordinates': [
                [
                    [-122.201872, 41.1562811],
                    [-122.201872, 3.240859],
                    [-118.7684233, 39.2490859],
                    [-118.7684233, 41.1562811],
                    [-122.201872, 41.1562811],
                ]
            ],
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert ut.get_west_most_point('foo.tiff') == -122.201872
        mock_info.assert_called_once_with('foo.tiff', format='json')

    info = {
        'wgs84Extent': {
            'type': 'Polygon',
            'coordinates': [
                [
                    [176.4143837, 53.0448494],
                    [176.4418596, 50.8863044],
                    [-179.4626094, 50.8340006],
                    [-179.2889357, 52.9883554],
                    [176.4143837, 53.0448494],
                ]
            ],
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert ut.get_west_most_point('bar.tiff') == -179.4626094
        mock_info.assert_called_once_with('bar.tiff', format='json')


def test_get_common_direction():
    assert ut.get_common_direction({1, 2, 3}) == 'ASCENDING'
    assert ut.get_common_direction({1, 873, 46986}) == 'ASCENDING'
    assert ut.get_common_direction({68, 69, 70}) == 'DESCENDING'
    with pytest.raises(ValueError):
        ut.get_common_direction({67, 68})

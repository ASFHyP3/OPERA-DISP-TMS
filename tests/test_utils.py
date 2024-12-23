from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
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


def test_transform_point():
    wkt_4326 = ut.wkt_from_epsg(4326)
    wkt_3857 = ut.wkt_from_epsg(3857)
    test_point = (-110, 45)

    transformed1 = ut.transform_point(*test_point, wkt_4326, wkt_4326)
    assert np.isclose(test_point, transformed1).all()

    transformed2 = ut.transform_point(*test_point, wkt_4326, wkt_3857)
    test_point_recreated = ut.transform_point(*transformed2, wkt_3857, wkt_4326)
    assert np.isclose(test_point, test_point_recreated).all()


def test_create_buffered_bbox():
    geotransform = (0, 1, 0, 0, 0, -1)
    shape = (10, 10)
    buffer_size = 1
    bbox = ut.create_buffered_bbox(geotransform, shape, buffer_size)
    assert bbox == (-1, -11, 11, 1)


def test_validate_bbox():
    with pytest.raises(ValueError, match='Bounding box must have 4 elements'):
        ut.validate_bbox([1, 2, 3])

    with pytest.raises(ValueError, match='Bounding box must be integers'):
        ut.validate_bbox([1, 2.0, 3, 4])

    with pytest.raises(ValueError, match='Bounding box minx is greater than maxx'):
        ut.validate_bbox([2, 2, 1, 4])

    with pytest.raises(ValueError, match='Bounding box miny is greater than maxy'):
        ut.validate_bbox([1, 4, 3, 2])

    ut.validate_bbox([1, 2, 3, 4])


def test_create_product_name():
    metadata_name = 'METADATA_ASCENDING_N41W124.tif'
    begin_date = datetime(2021, 1, 1)
    end_date = datetime(2021, 1, 2)
    product_name = ut.create_tile_name(metadata_name, begin_date, end_date)
    assert product_name == 'SW_CUMUL_DISP_20210101_20210102_ASCENDING_N41W124.tif'


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
    file_to_upload = tmp_path / 'subdir1' / 'subdir2' / 'myFile.txt'
    Path(file_to_upload).parent.mkdir(parents=True, exist_ok=True)
    file_to_upload.touch()
    with patch.object(ut, 'upload_file_to_s3') as mock_upload:
        mock_upload.return_value = []
        ut.upload_dir_to_s3(tmp_path, 'myBucket', 'myPrefix')
        mock_upload.assert_called_once_with(file_to_upload, 'myBucket', 'myPrefix/subdir1/subdir2/myFile.txt')

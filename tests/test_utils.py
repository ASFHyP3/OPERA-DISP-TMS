from datetime import datetime
from pathlib import Path
from unittest.mock import patch

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
    file_to_upload = tmp_path / 'subdir1' / 'subdir2' / 'myFile.txt'
    Path(file_to_upload).parent.mkdir(parents=True, exist_ok=True)
    file_to_upload.touch()
    with patch.object(ut, 'upload_file_to_s3') as mock_upload:
        mock_upload.return_value = []
        ut.upload_dir_to_s3(tmp_path, 'myBucket', 'myPrefix')
        mock_upload.assert_called_once_with(file_to_upload, 'myBucket', 'myPrefix/subdir1/subdir2/myFile.txt')

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from opera_disp_tms import tmp_s3_access


@pytest.fixture()
def example_credentials():
    expire_time = datetime.now(timezone.utc) + timedelta(hours=1)
    example_credentials = {
        'accessKeyId': 'foo',
        'secretAccessKey': 'bar',
        'sessionToken': 'baz',
        'expiration': expire_time.isoformat(),
    }
    yield example_credentials


def test_get_credentials(tmpdir, example_credentials):
    tea_url = 'https://fake.com/s3credentials'
    credential_file = Path(tmpdir) / 'credentials.json'
    credential_file.write_text(json.dumps(example_credentials))
    output_file = tmp_s3_access.get_credentials(creds_path=credential_file)
    assert output_file['accessKeyId'] == 'foo'

    example_credentials['expiration'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    credential_file.write_text(json.dumps(example_credentials))
    with patch('opera_disp_tms.tmp_s3_access.get_tmp_access_keys', return_value={}) as mock_func:
        tmp_s3_access.get_credentials(tea_url=tea_url, creds_path=credential_file)
        mock_func.assert_called_once_with(tea_url=tea_url, creds_path=credential_file)

    credential_file.unlink()
    with patch('opera_disp_tms.tmp_s3_access.get_tmp_access_keys', return_value={}) as mock_func:
        tmp_s3_access.get_credentials(tea_url=tea_url, creds_path=credential_file)
        mock_func.assert_called_once_with(tea_url=tea_url, creds_path=credential_file)

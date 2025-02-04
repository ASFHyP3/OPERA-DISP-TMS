from unittest.mock import patch

import responses

import opera_disp_tms.tmp_s3_access as tmp_s3_access


def test_get_temporary_aws_credentials():
    with responses.RequestsMock() as rsps:
        rsps.get(
            'https://cumulus.asf.alaska.edu/s3credentials',
            match=[responses.matchers.header_matcher({'Authorization': 'Bearer myToken'})],
            status=200,
            json={'foo': 'bar'},
        )

        with patch('opera_disp_tms.utils.get_edl_bearer_token', return_value='myToken') as mock_token:
            assert tmp_s3_access.get_temporary_aws_credentials() == {'foo': 'bar'}
            assert mock_token.call_count == 1

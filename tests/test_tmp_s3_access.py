import responses

import opera_disp_tms.tmp_s3_access as tmp_s3_access


@responses.activate
def test_get_temporary_aws_credentials():
    responses.get(
        'https://cumulus-test.asf.alaska.edu/s3credentials',
        status=200,
        json={'foo': 'bar'},
    )

    assert tmp_s3_access.get_temporary_aws_credentials() == {'foo': 'bar'}


@responses.activate
def test_get_temporary_aws_credentials_env(monkeypatch):
    monkeypatch.setenv('EARTHDATA_USERNAME', 'user')
    monkeypatch.setenv('EARTHDATA_PASSWORD', 'pass')
    responses.get(
        'https://cumulus-test.asf.alaska.edu/s3credentials',
        status=301,
        headers={'Location': 'https://uat.urs.earthdata.nasa.gov/oauth/authorize?foo=bar'},
    )
    responses.get(
        'https://uat.urs.earthdata.nasa.gov/oauth/authorize',
        status=401,
    )
    responses.get(
        'https://uat.urs.earthdata.nasa.gov/oauth/authorize',
        match=[responses.matchers.header_matcher({'Authorization': 'Basic dXNlcjpwYXNz'})],
        status=200,
        json={'foo': 'bar'},
    )

    assert tmp_s3_access.get_temporary_aws_credentials() == {'foo': 'bar'}

from datetime import datetime
from unittest.mock import patch

import responses

from opera_disp_tms import search


def test_from_umm():
    umm: dict = {
        'meta': {'native-id': 'mock-scene-name'},
        'umm': {
            'TemporalExtent': {
                'RangeDateTime': {'BeginningDateTime': '2019-10-06T00:26:42Z', 'EndingDateTime': '2020-09-30T00:26:48Z'}
            },
            'AdditionalAttributes': [
                {'Name': 'FRAME_NUMBER', 'Values': ['8882']},
                {'Name': 'ASCENDING_DESCENDING', 'Values': ['ASCENDING']},
            ],
            'RelatedUrls': [
                {'URL': 'mock-url', 'Type': 'GET DATA'},
                {'URL': 'mock-s3-uri', 'Type': 'GET DATA VIA DIRECT ACCESS'},
            ],
            'DataGranule': {'ProductionDateTime': '2024-10-29T21:36:46Z'},
        },
    }
    assert search.Granule.from_umm(umm) == search.Granule(
        scene_name='mock-scene-name',
        frame_id=8882,
        orbit_pass='ASCENDING',
        url='mock-url',
        s3_uri='mock-s3-uri',
        reference_date=datetime(2019, 10, 6, 0, 26, 42),
        secondary_date=datetime(2020, 9, 30, 0, 26, 48),
        creation_date=datetime(2024, 10, 29, 21, 36, 46),
    )

    umm['umm']['AdditionalAttributes'] = [
        {'Name': 'FRAME_NUMBER', 'Values': ['9154']},
        {'Name': 'ASCENDING_DESCENDING', 'Values': ['DESCENDING']},
    ]
    assert search.Granule.from_umm(umm) == search.Granule(
        scene_name='mock-scene-name',
        frame_id=9154,
        orbit_pass='DESCENDING',
        url='mock-url',
        s3_uri='mock-s3-uri',
        reference_date=datetime(2019, 10, 6, 0, 26, 42),
        secondary_date=datetime(2020, 9, 30, 0, 26, 48),
        creation_date=datetime(2024, 10, 29, 21, 36, 46),
    )


def test_get_cmr_metadata():
    with responses.RequestsMock() as rsps:
        params = {
            'short_name': 'OPERA_L3_DISP-S1_V1',
            'attribute[]': ['int,FRAME_NUMBER,123', 'float,PRODUCT_VERSION,0.9,'],
            'page_size': 2000,
        }

        rsps.get(
            'https://cmr.earthdata.nasa.gov/search/granules.umm_json',
            match=[
                responses.matchers.header_matcher({'Authorization': 'Bearer myToken'}),
                responses.matchers.query_param_matcher(params),
            ],
            status=200,
            json={'items': [{'id': 1}, {'id': 2}, {'id': 3}]},
            headers={'CMR-Search-After': 'cmr-s-a'},
        )

        rsps.get(
            'https://cmr.earthdata.nasa.gov/search/granules.umm_json',
            match=[
                responses.matchers.header_matcher({'Authorization': 'Bearer myToken', 'CMR-Search-After': 'cmr-s-a'}),
                responses.matchers.query_param_matcher(params),
            ],
            status=200,
            json={'items': [{'id': 4}, {'id': 5}]},
        )

        with patch('opera_disp_tms.utils.get_edl_bearer_token', return_value='myToken') as mock_token:
            assert search.get_cmr_metadata(frame_id=123) == [{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}, {'id': 5}]
            assert mock_token.call_count == 1

from datetime import datetime

import responses

from opera_disp_tms.search import Granule, eliminate_duplicates, filter_identical, get_cmr_metadata, is_redundant


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
    assert Granule.from_umm(umm) == Granule(
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
    assert Granule.from_umm(umm) == Granule(
        scene_name='mock-scene-name',
        frame_id=9154,
        orbit_pass='DESCENDING',
        url='mock-url',
        s3_uri='mock-s3-uri',
        reference_date=datetime(2019, 10, 6, 0, 26, 42),
        secondary_date=datetime(2020, 9, 30, 0, 26, 48),
        creation_date=datetime(2024, 10, 29, 21, 36, 46),
    )


def make_granule(name, ref, sec, creation, frame_id=0):
    return Granule(
        scene_name=name,
        reference_date=ref,
        secondary_date=sec,
        creation_date=creation,
        frame_id=frame_id,
        orbit_pass='',
        url='',
        s3_uri='',
    )


def test_eliminate_duplicates():
    assert eliminate_duplicates([]) == []

    granules = [
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 1)),
    ]
    assert eliminate_duplicates(granules) == granules

    granules = [
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3)),
        make_granule('C', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 4)),
        make_granule('D', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 2)),
    ]
    assert eliminate_duplicates(granules) == [granules[2]]

    granules = [
        make_granule('A', datetime(1, 1, 2, 0, 0, 1), datetime(1, 1, 5), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 3)),
    ]
    assert eliminate_duplicates(granules) == granules

    granules = [
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 2), datetime(1, 1, 4), datetime(1, 1, 3)),
        make_granule('A', datetime(2, 1, 1), datetime(1, 1, 5), datetime(1, 1, 1)),
        make_granule('B', datetime(2, 1, 1), datetime(1, 1, 4), datetime(1, 1, 3)),
    ]

    assert eliminate_duplicates(granules) == [granules[1], granules[3]]

    granules = [
        make_granule('A', datetime(1, 1, 5), datetime(1, 1, 8), datetime(1, 1, 6)),
        make_granule('B', datetime(1, 1, 6, 0, 0, 1), datetime(1, 1, 8), datetime(1, 1, 6)),
        make_granule('C', datetime(1, 1, 6), datetime(1, 1, 9, 0, 0, 1), datetime(1, 1, 6)),
        make_granule('D', datetime(1, 1, 5), datetime(1, 1, 8), datetime(1, 1, 6), frame_id=1),
        make_granule('A', datetime(1, 1, 5), datetime(1, 1, 8), datetime(1, 1, 6)),
        make_granule('E', datetime(1, 1, 5), datetime(1, 1, 8), datetime(1, 1, 6)),
        make_granule('F', datetime(1, 1, 4), datetime(1, 1, 8), datetime(1, 1, 5)),
        make_granule('G', datetime(1, 1, 6), datetime(1, 1, 8), datetime(1, 1, 5)),
        make_granule('H', datetime(1, 1, 5), datetime(1, 1, 7), datetime(1, 1, 5)),
        make_granule('I', datetime(1, 1, 5), datetime(1, 1, 9), datetime(1, 1, 5)),
        make_granule('J', datetime(1, 1, 5), datetime(1, 1, 8), datetime(1, 1, 5)),
        make_granule('K', datetime(1, 1, 6), datetime(1, 1, 9), datetime(1, 1, 5)),
    ]
    assert eliminate_duplicates(granules) == granules[0:4]


def test_filter_identical():
    assert filter_identical([]) == []

    granule = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 1))

    assert filter_identical([granule]) == [granule]

    granules = [
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 1), frame_id=1),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 1), frame_id=2),
        make_granule('C', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 1), frame_id=3),
    ]
    assert filter_identical(granules) == granules

    granules = [
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3)),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3)),
        make_granule('C', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3)),
        make_granule('D', datetime(2, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3)),
        make_granule('E', datetime(2, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3)),
        make_granule('F', datetime(2, 1, 1), datetime(3, 1, 2), datetime(1, 1, 3)),
    ]

    assert filter_identical(granules) == [granules[0], granules[3], granules[5]]


def test_is_redundant():
    assert is_redundant(
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 2), datetime(1, 1, 4), datetime(1, 1, 3)),
    )

    assert is_redundant(
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 5), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 3)),
    )

    assert is_redundant(
        make_granule('A', datetime(1, 1, 2), datetime(1, 1, 5), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 3)),
    )

    assert not is_redundant(
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 3)),
        make_granule('A', datetime(1, 1, 2), datetime(1, 1, 5), datetime(1, 1, 1)),
    )

    assert not is_redundant(
        make_granule('A', datetime(1, 1, 3), datetime(1, 1, 5), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 3)),
    )

    assert not is_redundant(
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 6), datetime(1, 1, 1)),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 4), datetime(1, 1, 3)),
    )

    assert not is_redundant(
        make_granule('A', datetime(1, 1, 1), datetime(1, 1, 1), datetime(1, 1, 1), frame_id=1),
        make_granule('B', datetime(1, 1, 1), datetime(1, 1, 1), datetime(1, 1, 1), frame_id=2),
    )


def test__eq__():
    granule1 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3))
    granule2 = make_granule('B', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3))
    assert granule1 == granule2

    granule1 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3))
    granule2 = make_granule('A', datetime(1, 1, 2), datetime(1, 1, 2), datetime(1, 1, 3))
    assert not granule1 == granule2

    granule1 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3))
    granule2 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 3), datetime(1, 1, 3))
    assert not granule1 == granule2

    granule1 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3))
    granule2 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 5))
    assert not granule1 == granule2

    granule1 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3), frame_id=0)
    granule2 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3), frame_id=1)
    assert not granule1 == granule2

    granule1 = make_granule('A', datetime(1, 1, 1), datetime(1, 1, 2), datetime(1, 1, 3))
    assert not granule1 == 'foo'


def test_get_cmr_metadata():
    with responses.RequestsMock() as rsps:
        params = {
            'short_name': 'OPERA_L3_DISP-S1_V1',
            'attribute[]': 'int,FRAME_NUMBER,123',
            'page_size': '2000',
        }

        rsps.get(
            'https://cmr.earthdata.nasa.gov/search/granules.umm_json',
            match=[responses.matchers.query_param_matcher(params)],
            status=200,
            json={'items': [{'id': 1}, {'id': 2}, {'id': 3}]},
            headers={'CMR-Search-After': 'cmr-s-a'},
        )

        rsps.get(
            'https://cmr.earthdata.nasa.gov/search/granules.umm_json',
            match=[
                responses.matchers.query_param_matcher(params),
                responses.matchers.header_matcher({'CMR-Search-After': 'cmr-s-a'}),
            ],
            status=200,
            json={'items': [{'id': 4}, {'id': 5}]},
        )

        assert get_cmr_metadata(frame_id=123) == [{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}, {'id': 5}]

from datetime import datetime

from opera_disp_tms.search import Granule


def test_from_umm():
    umm = {
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

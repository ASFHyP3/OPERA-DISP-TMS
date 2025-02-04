from opera_disp_tms import create_measurement_geotiff, create_tile_map


def test_create_tile_map_parser():
    parser = create_tile_map.make_parser()

    args = parser.parse_args(
        [
            'displacement',
            '--bucket',
            'myBucket',
            '--bucket-prefix',
            'myPrefix',
        ]
    )

    assert args.measurement_type == 'displacement'
    assert args.bucket == 'myBucket'
    assert args.bucket_prefix == 'myPrefix'


def test_create_measurement_geotiff_parser():
    parser = create_measurement_geotiff.make_parser()

    args = parser.parse_args(
        [
            '11113',
            'secant_velocity',
            '20140101',
            '20260101',
            '--bucket',
            'myBucket',
            '--bucket-prefix',
            'myPrefix',
        ]
    )

    assert args.frame_id == 11113
    assert args.measurement_type == 'secant_velocity'
    assert args.bucket == 'myBucket'
    assert args.bucket_prefix == 'myPrefix'
    assert args.begin_date == '20140101'
    assert args.end_date == '20260101'

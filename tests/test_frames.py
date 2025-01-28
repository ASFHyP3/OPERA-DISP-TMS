from unittest.mock import patch

from shapely.geometry import box

from opera_disp_tms import frames


def test_frame_from_row():
    row = (1, 32610, 123, 'ASCENDING', True, False, 'POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))')
    frame = frames.Frame.from_row(row)
    assert frame.frame_id == 1
    assert frame.epsg == 32610
    assert frame.relative_orbit_number == 123
    assert frame.orbit_pass == 'ASCENDING'
    assert frame.is_land is True
    assert frame.is_north_america is False
    assert frame.geom.bounds == box(0, 0, 1, 1).bounds


def test_download_frame_db(tmp_path):
    with patch('opera_disp_tms.frames.download_file') as mock_download_file:
        db_path = tmp_path / 'test.gpkg'
        frames.download_frame_db(db_path)
        assert mock_download_file.call_count == 1
        download_url = f'https://opera-disp-tms-dev.s3.us-west-2.amazonaws.com/{db_path.name}'
        assert mock_download_file.call_args[0][0] == download_url

    db_path.touch()
    with patch('opera_disp_tms.frames.download_file') as mock_download_file:
        frames.download_frame_db(db_path)
        assert mock_download_file.call_count == 0


def test_reorder_frames():
    # Ascending no anit-meridian
    frame_ids = frames.reorder_frames([5900, 25499, 5901, 25500])
    assert frame_ids == [5900, 5901, 25499, 25500]

    # Descending no anit-meridian
    frame_ids = frames.reorder_frames([39073, 19472, 19473, 39072])
    assert frame_ids == [39072, 39073, 19472, 19473]

    # Ascending anit-meridian
    frame_ids = frames.reorder_frames([45098, 25501, 45099, 25500])
    assert frame_ids == [25500, 25501, 45098, 45099]

    # Descending anit-meridian
    frame_ids = frames.reorder_frames([39075, 11688, 39074, 11689])
    assert frame_ids == [11688, 11689, 39074, 39075]


def test_sort_geotiffs():
    geotiffs = [
        'displacement_05900_20220101_20220131.tif',
        'displacement_25499_20220101_20220131.tif',
        'displacement_05901_20220101_20220131.tif',
        'displacement_25500_20220101_20220131.tif',
    ]
    golden_sorted_geotiffs = [
        'displacement_05900_20220101_20220131.tif',
        'displacement_05901_20220101_20220131.tif',
        'displacement_25499_20220101_20220131.tif',
        'displacement_25500_20220101_20220131.tif',
    ]
    sorted_geotiffs = frames.sort_geotiffs(geotiffs)
    assert sorted_geotiffs == golden_sorted_geotiffs

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
    assert frame.geom.bounds == frames.box(0, 0, 1, 1).bounds


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


def test_build_query():
    bbox = (0, 0, 1, 1)
    wkt_str = box(*bbox).wkt
    query, params = frames.build_query(bbox)
    assert params == [wkt_str]

    query, params = frames.build_query(bbox, orbit_pass='ASCENDING')
    assert ' AND orbit_pass = ?' in query.splitlines()[-1]
    assert params == [wkt_str, 'ASCENDING']

    query, params = frames.build_query(bbox, is_north_america=True)
    assert ' AND is_north_america = ?' in query.splitlines()[-1]
    assert params == [wkt_str, 1]

    query, params = frames.build_query(bbox, is_land=False)
    assert ' AND is_land = ?' in query.splitlines()[-1]
    assert params == [wkt_str, 0]


# FIXME: Remove when updating to OPERA DISP data v0.9
def test_get_orbit_pass():
    assert frames.get_orbit_pass(9154) == 'ASCENDING'
    assert frames.get_orbit_pass(3325) == 'DESCENDING'

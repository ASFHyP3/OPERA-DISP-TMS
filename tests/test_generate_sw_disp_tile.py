from collections import namedtuple
from datetime import datetime
from unittest import mock
from unittest.mock import patch

import rioxarray  # noqa
import xarray as xr
from osgeo import gdal

from opera_disp_tms import generate_sw_disp_tile as sw


def create_tif(save_path, metadata):
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(str(save_path), 1, 1, 1, gdal.GDT_Byte)
    ds.SetMetadata(metadata)
    ds = None


def test_extract_frame_metadata():
    metadata = {
        'OPERA_FRAMES': '1, 2',
        'FRAME_1_REF_TIME': '20210101T000000Z',
        'FRAME_1_REF_POINT_EASTINGNORTHING': '1, 2',
        'FRAME_2_REF_TIME': '20210102T000000Z',
        'FRAME_2_REF_POINT_EASTINGNORTHING': '3, 4',
    }

    expected = sw.FrameMeta(1, datetime(2021, 1, 1), (1, 2))
    assert sw.extract_frame_metadata(metadata, 1) == expected

    expected = sw.FrameMeta(2, datetime(2021, 1, 2), (3, 4))
    assert sw.extract_frame_metadata(metadata, 2) == expected


def test_frames_from_metadata(tmp_path):
    tmp_tif = tmp_path / 'test.tif'
    metadata = {
        'OPERA_FRAMES': '1, 2',
        'FRAME_1_REF_TIME': '20210101T000000Z',
        'FRAME_1_REF_POINT_EASTINGNORTHING': '1, 2',
        'FRAME_2_REF_TIME': '20210102T000000Z',
        'FRAME_2_REF_POINT_EASTINGNORTHING': '3, 4',
    }
    create_tif(tmp_tif, metadata)
    frames = sw.frames_from_metadata(tmp_tif)
    assert len(frames) == 2
    assert frames[1].frame_id == 1
    assert frames[1].reference_date == datetime(2021, 1, 1, 0, 0, 0)
    assert frames[1].reference_point_eastingnorthing == (1, 2)
    assert frames[2].frame_id == 2
    assert frames[2].reference_date == datetime(2021, 1, 2, 0, 0, 0)
    assert frames[2].reference_point_eastingnorthing == (3, 4)


def test_find_needed_granules():
    GranuleStub = namedtuple('GranuleStub', ['frame_id', 'secondary_date'])
    granules = [
        GranuleStub(frame_id=1, secondary_date=datetime(2021, 1, 1)),
        GranuleStub(frame_id=1, secondary_date=datetime(2021, 1, 2)),
        GranuleStub(frame_id=1, secondary_date=datetime(2021, 1, 3)),
    ]

    fn_name = 'opera_disp_tms.generate_sw_disp_tile.find_granules_for_frame'
    with mock.patch(fn_name, return_value=granules):
        needed_granules = sw.find_needed_granules([1], datetime(2021, 1, 1), datetime(2021, 1, 3), strategy='max')
        assert len(needed_granules[1]) == 1
        assert needed_granules[1] == [granules[2]]

        needed_granules = sw.find_needed_granules([1], datetime(2021, 1, 1), datetime(2021, 1, 3), strategy='minmax')
        assert len(needed_granules[1]) == 2
        assert needed_granules[1] == [granules[0], granules[2]]

        needed_granules = sw.find_needed_granules([1], datetime(2021, 1, 1), datetime(2021, 1, 3), strategy='all')
        assert len(needed_granules[1]) == 3
        assert needed_granules[1] == granules


def test_update_reference_date():
    def make_xr(value, ref_date):
        dim_coords = dict(dims=['x'], coords={'x': [1]})
        attrs = {'reference_date': ref_date, 'bbox': [0, 0, 0, 0]}
        out = xr.DataArray([value], **dim_coords, attrs=attrs)
        return out

    to_correct = make_xr(2, datetime(2021, 1, 1))
    back1 = make_xr(4, datetime(2020, 1, 1))
    back2 = make_xr(7, datetime(2019, 1, 1))

    frame = sw.FrameMeta(1, datetime(2020, 1, 1), (0, 0))
    pkg = 'opera_disp_tms.generate_sw_disp_tile'
    with patch(f'{pkg}.find_needed_granules') as mock_find, patch(f'{pkg}.load_sw_disp_granule') as mock_load:
        mock_find.return_value = {1: [None]}
        mock_load.side_effect = [back1, back2]
        to_correct = sw.update_reference_date(to_correct, frame)
        assert to_correct.attrs['reference_date'] == datetime(2020, 1, 1)
        assert to_correct.values == 6

    to_correct = make_xr(2, datetime(2021, 1, 1))
    frame = sw.FrameMeta(1, datetime(2019, 1, 1), (0, 0))
    pkg = 'opera_disp_tms.generate_sw_disp_tile'
    with patch(f'{pkg}.find_needed_granules') as mock_find, patch(f'{pkg}.load_sw_disp_granule') as mock_load:
        mock_find.return_value = {1: [None]}
        mock_load.side_effect = [back1, back2]
        to_correct = sw.update_reference_date(to_correct, frame)
        assert to_correct.attrs['reference_date'] == datetime(2019, 1, 1)
        assert to_correct.values == 13

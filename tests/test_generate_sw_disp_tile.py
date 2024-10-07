from collections import namedtuple
from datetime import datetime
from unittest import mock

import numpy as np
import pytest
import rioxarray  # noqa
import xarray as xr
from osgeo import gdal

from opera_disp_tms import generate_sw_disp_tile as sw
from opera_disp_tms import utils


def create_tif(save_path, metadata):
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(str(save_path), 1, 1, 1, gdal.GDT_Byte)
    ds.SetMetadata(metadata)
    ds = None


def test_extract_frame_metadata():
    metadata = {
        'OPERA_FRAMES': '1, 2',
        'FRAME_1_REF_TIME': '20210101T000000Z',
        'FRAME_1_REF_POINT_ARRAY': '1, 2',
        'FRAME_1_REF_POINT_GEO': '1.0, 2.0',
        'FRAME_2_REF_TIME': '20210102T000000Z',
        'FRAME_2_REF_POINT_ARRAY': '3, 4',
        'FRAME_2_REF_POINT_GEO': '3.0, 4.0',
    }

    expected = sw.FrameMeta(1, datetime(2021, 1, 1), (1, 2), (1.0, 2.0))
    assert sw.extract_frame_metadata(metadata, 1) == expected

    expected = sw.FrameMeta(2, datetime(2021, 1, 2), (3, 4), (3.0, 4.0))
    assert sw.extract_frame_metadata(metadata, 2) == expected


def test_frames_from_metadata(tmp_path):
    tmp_tif = tmp_path / 'test.tif'
    metadata = {
        'OPERA_FRAMES': '1, 2',
        'FRAME_1_REF_TIME': '20210101T000000Z',
        'FRAME_1_REF_POINT_ARRAY': '1, 2',
        'FRAME_1_REF_POINT_GEO': '1.0, 2.0',
        'FRAME_2_REF_TIME': '20210102T000000Z',
        'FRAME_2_REF_POINT_ARRAY': '3, 4',
        'FRAME_2_REF_POINT_GEO': '3.0, 4.0',
    }
    create_tif(tmp_tif, metadata)
    frames = sw.frames_from_metadata(tmp_tif)
    assert len(frames) == 2
    assert frames[1].frame_id == 1
    assert frames[1].reference_date == datetime(2021, 1, 1, 0, 0, 0)
    assert frames[1].reference_point_array == (1, 2)
    assert frames[1].reference_point_geo == (1.0, 2.0)
    assert frames[2].frame_id == 2
    assert frames[2].reference_date == datetime(2021, 1, 2, 0, 0, 0)
    assert frames[2].reference_point_array == (3, 4)
    assert frames[2].reference_point_geo == (3.0, 4.0)


def test_find_needed_granules():
    GranuleStub = namedtuple('GranuleStub', ['frame_id', 'secondary_date'])
    granules = [
        GranuleStub(frame_id=1, secondary_date=datetime(2021, 1, 1)),
        GranuleStub(frame_id=1, secondary_date=datetime(2021, 1, 2)),
        GranuleStub(frame_id=2, secondary_date=datetime(2021, 1, 1)),
        GranuleStub(frame_id=2, secondary_date=datetime(2021, 1, 2)),
    ]
    with mock.patch('opera_disp_tms.generate_sw_disp_tile.find_california_dataset', return_value=granules):
        needed_granules = sw.find_needed_granules([1], datetime(2021, 1, 1), datetime(2021, 1, 2))

    assert len(needed_granules) == 1
    assert needed_granules[0] == granules[1]

    with mock.patch('opera_disp_tms.generate_sw_disp_tile.find_california_dataset', return_value=granules):
        needed_granules = sw.find_needed_granules([1, 2], datetime(2021, 1, 1), datetime(2021, 1, 2))

    assert len(needed_granules) == 2
    assert needed_granules[0] == granules[1]
    assert needed_granules[1] == granules[3]


def test_update_spatiotemporal_reference():
    data = [[3, 2], [1, 0]]
    tmp_array = xr.DataArray(data, coords={'y': [1.0, 2.0], 'x': [1.0, 2.0]})
    tmp_array.attrs['frame_id'] = 1
    tmp_array.attrs['reference_date'] = datetime(2021, 1, 1)
    new_x, new_y = utils.transform_point(2, 2, utils.wkt_from_epsg(26910), utils.wkt_from_epsg(4326))
    tmp_array.attrs['reference_point_geo'] = (new_x, new_y)
    tmp_array.rio.write_crs(utils.wkt_from_epsg(26910), inplace=True)

    ref_x, ref_y = utils.transform_point(1, 1, utils.wkt_from_epsg(26910), utils.wkt_from_epsg(4326))
    frame = sw.FrameMeta(1, datetime(2021, 1, 1), (0, 0), (ref_x, ref_y))

    updated_array = sw.update_spatiotemporal_reference(tmp_array, frame)
    assert np.all(updated_array.data == np.array([[0, -1], [-2, -3]]))
    assert updated_array.attrs['reference_point_geo'] == frame.reference_point_geo

    tmp_array.attrs['reference_date'] = datetime(2021, 1, 2)
    with pytest.raises(NotImplementedError):
        updated_array = sw.update_spatiotemporal_reference(tmp_array, frame)


def test_create_product_name():
    metadata_name = 'METADATA_ASCENDING_N41W124.tif'
    begin_date = datetime(2021, 1, 1)
    end_date = datetime(2021, 1, 2)
    product_name = sw.create_product_name(metadata_name, begin_date, end_date)
    assert product_name == 'SW_CUMUL_DISP_20210101_20210102_ASCENDING_N41W124.tif'

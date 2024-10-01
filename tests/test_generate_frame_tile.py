"""Test functions in generate_frame_tile.py"""
from collections import namedtuple

import numpy as np
import pytest
from osgeo import gdal
from shapely.geometry import Polygon

from opera_disp_tms import generate_frame_tile


gdal.UseExceptions()


def test_check_bbox_all_int():
    with pytest.raises(ValueError):
        generate_frame_tile.check_bbox_all_int([1, 2.0, 3])
    generate_frame_tile.check_bbox_all_int([1, 2, 3])


def test_create_product_name():
    name = generate_frame_tile.create_product_name(['ONE', 'TWO'], 'ASC', [1, 2, 3, 4])
    assert name == 'ONE_TWO_ASC_N02E001_N04E003'

    name = generate_frame_tile.create_product_name(['ONE', 'TWO'], 'ASC', [-1, -2, -3, -4])
    assert name == 'ONE_TWO_ASC_S02W001_S04W003'


def test_reorder_frames():
    Geom = namedtuple('Geom', ['bounds'])
    StubFrame = namedtuple('StubFrame', ['relative_orbit_number', 'frame_id', 'geom', 'orbit_pass'])

    frame_asc = StubFrame(1, 1, Geom([0, 0, 1, 1]), 'ASC')
    frame_des = StubFrame(1, 1, Geom([0, 0, 1, 1]), 'DES')
    with pytest.raises(ValueError):
        generate_frame_tile.reorder_frames([frame_asc, frame_des])

    frame_1_1 = StubFrame(1, 1, Geom([1, 1, 2, 2]), 'ASC')
    frame_1_2 = StubFrame(1, 2, Geom([3, 3, 4, 4]), 'ASC')
    frame_2_3 = StubFrame(2, 3, Geom([0, 0, 2, 2]), 'ASC')
    frame_2_4 = StubFrame(2, 4, Geom([2, 2, 3, 3]), 'ASC')

    result = generate_frame_tile.reorder_frames([frame_2_4, frame_1_2, frame_2_3, frame_1_1], order_by='frame_number')
    assert result == [frame_2_4, frame_2_3, frame_1_2, frame_1_1]

    result = generate_frame_tile.reorder_frames([frame_2_4, frame_1_2, frame_2_3, frame_1_1], order_by='west_most')
    assert result == [frame_1_2, frame_1_1, frame_2_4, frame_2_3]

    frame_1_anti = StubFrame(1, 1, Geom([-1, -1, 1, 1]), 'ASC')
    frame_2_norm = StubFrame(2, 1, Geom([0, 0, 2, 2]), 'ASC')
    assert generate_frame_tile.reorder_frames([frame_1_anti, frame_2_norm], order_by='west_most') == [
        frame_2_norm,
        frame_1_anti,
    ]


def test_create_empty_tile_frame(tmp_path):
    test_tif = tmp_path / 'test.tif'
    generate_frame_tile.create_empty_frame_tile([1, 1, 2, 2], test_tif)
    assert test_tif.exists()

    info = gdal.Info(str(test_tif), options=['-json'])
    assert info['driverShortName'] == 'GTiff'
    assert info['metadata']['IMAGE_STRUCTURE']['COMPRESSION'] == 'LZW'
    assert 'ID["EPSG",3857]' in info['coordinateSystem']['wkt']
    assert info['wgs84Extent']
    lat_lon_bounds = Polygon(info['wgs84Extent']['coordinates'][0]).bounds
    assert np.isclose(lat_lon_bounds, [1, 1, 2, 2], rtol=1e-4).all()

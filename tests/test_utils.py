from datetime import datetime

import numpy as np
import pytest

import opera_disp_tms.utils as ut


def test_round_to_day():
    assert ut.round_to_day(datetime(2021, 1, 1, 12, 1, 1)) == datetime(2021, 1, 2, 0, 0, 0)
    assert ut.round_to_day(datetime(2021, 1, 1, 11, 1, 1)) == datetime(2021, 1, 1, 0, 0, 0)


def test_transform_point():
    wkt_4326 = ut.wkt_from_epsg(4326)
    wkt_3857 = ut.wkt_from_epsg(3857)
    test_point = (-110, 45)

    transformed1 = ut.transform_point(*test_point, wkt_4326, wkt_4326)
    assert np.isclose(test_point, transformed1).all()

    transformed2 = ut.transform_point(*test_point, wkt_4326, wkt_3857)
    test_point_recreated = ut.transform_point(*transformed2, wkt_3857, wkt_4326)
    assert np.isclose(test_point, test_point_recreated).all()


def test_create_buffered_bbox():
    geotransform = (0, 1, 0, 0, 0, -1)
    shape = (10, 10)
    buffer_size = 1
    bbox = ut.create_buffered_bbox(geotransform, shape, buffer_size)
    assert bbox == (-1, -11, 11, 1)


def test_validate_bbox():
    with pytest.raises(ValueError, match='Bounding box must have 4 elements'):
        ut.validate_bbox([1, 2, 3])

    with pytest.raises(ValueError, match='Bounding box must be integers'):
        ut.validate_bbox([1, 2.0, 3, 4])

    with pytest.raises(ValueError, match='Bounding box minx is greater than maxx'):
        ut.validate_bbox([2, 2, 1, 4])

    with pytest.raises(ValueError, match='Bounding box miny is greater than maxy'):
        ut.validate_bbox([1, 4, 3, 2])

    ut.validate_bbox([1, 2, 3, 4])


def test_create_product_name():
    metadata_name = 'METADATA_ASCENDING_N41W124.tif'
    begin_date = datetime(2021, 1, 1)
    end_date = datetime(2021, 1, 2)
    product_name = ut.create_tile_name(metadata_name, begin_date, end_date)
    assert product_name == 'SW_CUMUL_DISP_20210101_20210102_ASCENDING_N41W124.tif'

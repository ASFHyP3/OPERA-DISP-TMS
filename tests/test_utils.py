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


def test_check_bbox_all_int():
    with pytest.raises(ValueError, match='Bounding box must have 4 elements'):
        ut.check_bbox_all_int([1, 2, 3])

    with pytest.raises(ValueError, match='Bounding box must be integers'):
        ut.check_bbox_all_int([1, 2.0, 3, 4])

    with pytest.raises(ValueError, match='Bounding box minx is greater than maxx'):
        ut.check_bbox_all_int([2, 2, 1, 4])

    with pytest.raises(ValueError, match='Bounding box miny is greater than maxy'):
        ut.check_bbox_all_int([1, 4, 3, 2])

    ut.check_bbox_all_int([1, 2, 3, 4])

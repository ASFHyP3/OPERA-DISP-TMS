from datetime import datetime

import numpy as np

import opera_disp_tms.utils as ut


def test_round_to_day():
    assert ut.round_to_day(datetime(2021, 1, 1, 12, 1, 1)) == datetime(2021, 1, 2, 0, 0, 0)
    assert ut.round_to_day(datetime(2021, 1, 1, 11, 1, 1)) == datetime(2021, 1, 1, 0, 0, 0)


def test_transform_point():
    wkt_4326 = ut.wkt_from_epsg(4326)
    wkt_3857 = ut.wkt_from_epsg(3857)
    assert ut.transform_point(0, 0, wkt_4326, wkt_3857) == (0, 0)
    
    bilbo = (45, -120)
    there = ut.transform_point(*bilbo, wkt_4326, wkt_3857)
    and_back_agian = ut.transform_point(*there, wkt_3857, wkt_4326)
    assert np.isclose(bilbo, and_back_agian).all()

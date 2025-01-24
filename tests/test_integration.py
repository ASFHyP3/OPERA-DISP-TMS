from copy import deepcopy
from datetime import datetime

import numpy as np
import pytest

from opera_disp_tms import create_measurement_geotiff, prep_stack


@pytest.fixture(scope='module')
def frame_9156_xrs():
    bbox = (-13578500, 4496000, -13577500, 4497000)  # 1x1 km EPSG:3857 box near San Jose, CA
    granules = prep_stack.find_needed_granules(9156, datetime(2020, 1, 1), datetime(2025, 1, 1), 'spanning')
    granule_xrs = [prep_stack.load_sw_disp_granule(x, bbox) for x in granules]
    return granule_xrs


@pytest.mark.integration
def test_displacement(frame_9156_xrs):
    granule_xrs = deepcopy(frame_9156_xrs)
    row0_col0_disp_value = (
        0.0017032623291015625
        + -0.0007520914077758789
        + -0.0032019615173339844
        + 0.002876758575439453
        + -0.00011713802814483643
    )
    prep_stack.align_to_common_reference_date(granule_xrs, min(g.reference_date for g in granule_xrs))
    assert np.isclose(granule_xrs[-1].data[0, 0], row0_col0_disp_value)
    assert np.isnan(granule_xrs[-1].data[27, 14])


@pytest.mark.integration
def test_secant_velocity(frame_9156_xrs):
    granule_xrs = deepcopy(frame_9156_xrs)
    prep_stack.align_to_common_reference_date(granule_xrs, min(g.reference_date for g in granule_xrs))
    velocity = generate_sw_vel_tile.compute_velocity(granule_xrs, secant=True)

    delta_time = (granule_xrs[-1].secondary_date - granule_xrs[0].secondary_date).days / 365.25
    delta_disp = granule_xrs[-1].data[0, 0] - granule_xrs[0].data[0, 0]
    secant_slope = delta_disp / delta_time
    assert np.isclose(velocity.velocity.data[0, 0], secant_slope)
    assert np.isnan(velocity.velocity.data[27, 14])


@pytest.mark.integration
def test_velocity(frame_9156_xrs):
    granule_xrs = deepcopy(frame_9156_xrs)
    prep_stack.align_to_common_reference_date(granule_xrs, min(g.reference_date for g in granule_xrs))
    velocity = generate_sw_vel_tile.compute_velocity(granule_xrs, secant=False)
    years_since_start = [0.0, 1.00205339, 2.00410678, 3.03901437, 3.99178645, 4.68172485]
    displacements = [0.0, 0.00170326, 0.00095117, -0.00225079, 0.00062597, 0.00050883]
    design_matrix = np.vstack([years_since_start, np.ones_like(years_since_start)]).T
    slope = np.linalg.lstsq(design_matrix, displacements, rcond=None)[0][0]
    assert np.isclose(velocity.velocity.data[0, 0], slope)
    assert np.isnan(velocity.velocity.data[27, 14])

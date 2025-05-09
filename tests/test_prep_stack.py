from collections import namedtuple
from datetime import datetime
from unittest import mock

import numpy as np
import pytest
import rioxarray  # noqa
import xarray as xr

from opera_disp_tms import prep_stack


def test_find_needed_granules():
    GranuleStub = namedtuple(
        'GranuleStub', ['frame_id', 'scene_name', 'reference_date', 'secondary_date', 'creation_date']
    )
    granules = [
        GranuleStub(
            frame_id=1,
            scene_name='A',
            reference_date=datetime(2021, 1, 1),
            secondary_date=datetime(2021, 1, 3),
            creation_date=datetime(2021, 1, 3),
        ),
        GranuleStub(
            frame_id=1,
            scene_name='A',
            reference_date=datetime(2021, 1, 1),
            secondary_date=datetime(2021, 1, 5),
            creation_date=datetime(2021, 1, 5),
        ),
        GranuleStub(
            frame_id=1,
            scene_name='A',
            reference_date=datetime(2021, 1, 5),
            secondary_date=datetime(2021, 1, 8),
            creation_date=datetime(2021, 1, 8),
        ),
        GranuleStub(
            frame_id=1,
            scene_name='A',
            reference_date=datetime(2021, 1, 8),
            secondary_date=datetime(2021, 1, 11),
            creation_date=datetime(2021, 1, 11),
        ),
    ]
    fn_name = 'opera_disp_tms.prep_stack.find_granules_for_frame'

    with mock.patch(fn_name, return_value=granules):
        needed_granules = prep_stack.find_needed_granules(1, datetime(2021, 1, 1), datetime(2021, 1, 9), strategy='all')
        assert len(needed_granules) == 3
        assert needed_granules == granules[:3]

        needed_granules = prep_stack.find_needed_granules(
            1, datetime(2021, 1, 1), datetime(2021, 1, 9), strategy='spanning'
        )
        assert len(needed_granules) == 2
        assert needed_granules == granules[1:3]


def test_restrict_to_spanning_set():
    GranuleStub = namedtuple('GranuleStub', ['frame_id', 'reference_date', 'secondary_date'])
    granules = [
        GranuleStub(1, datetime(2021, 1, 1), datetime(2021, 1, 4)),
        GranuleStub(1, datetime(2021, 1, 4), datetime(2021, 1, 7)),
        GranuleStub(1, datetime(2021, 1, 7), datetime(2021, 1, 10)),
    ]
    result = prep_stack.restrict_to_spanning_set(granules)  # type: ignore[arg-type]
    assert len(result) == 3
    assert result == granules

    granules.append(GranuleStub(1, datetime(2021, 1, 7), datetime(2021, 1, 13)))
    result = prep_stack.restrict_to_spanning_set(granules)  # type: ignore[arg-type]
    assert len(result) == 3
    assert result == [granules[0], granules[1], granules[3]]

    with pytest.raises(ValueError, match='Granules do not form a spanning set.'):
        prep_stack.restrict_to_spanning_set([granules[0], granules[2], granules[3]])  # type: ignore[list-item]


def test_replace_nans_with_zeros():
    xrs = [
        xr.DataArray([[1.0, 0.0], [1.0, 0.0]]),
        xr.DataArray([[5.0, np.nan], [np.nan, 0.0]]),
        xr.DataArray([[-1.0, 0.0], [np.nan, np.nan]]),
        xr.DataArray([[7.0, 0.0], [1.0, np.nan]]),
        xr.DataArray([[-3.0, 1.0], [1.0, np.nan]]),
    ]

    expected = [
        xr.DataArray([[1.0, 0.0], [1.0, 0.0]]),
        xr.DataArray([[5.0, 0.0], [np.nan, 0.0]]),
        xr.DataArray([[-1.0, 0.0], [np.nan, np.nan]]),
        xr.DataArray([[7.0, 0.0], [1.0, np.nan]]),
        xr.DataArray([[-3.0, 1.0], [1.0, np.nan]]),
    ]
    prep_stack.replace_nans_with_zeros(xrs, minimum_valid_data_percent=0.8)
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        xr.DataArray([[1.0, 0.0], [1.0, 0.0]]),
        xr.DataArray([[5.0, np.nan], [np.nan, 0.0]]),
        xr.DataArray([[-1.0, 0.0], [np.nan, np.nan]]),
        xr.DataArray([[7.0, 0.0], [1.0, np.nan]]),
        xr.DataArray([[-3.0, 1.0], [1.0, np.nan]]),
    ]
    expected = [
        xr.DataArray([[1.0, 0.0], [1.0, 0.0]]),
        xr.DataArray([[5.0, 0.0], [0.0, 0.0]]),
        xr.DataArray([[-1.0, 0.0], [0.0, np.nan]]),
        xr.DataArray([[7.0, 0.0], [1.0, np.nan]]),
        xr.DataArray([[-3.0, 1.0], [1.0, np.nan]]),
    ]
    prep_stack.replace_nans_with_zeros(xrs, minimum_valid_data_percent=0.6)
    assert all(a.identical(b) for a, b in zip(xrs, expected))


def test_align_to_common_reference_date():
    def create_data_array(data, ref_date, sec_date):
        coords = {'x': [1, 2]}
        da = xr.DataArray(
            data=data,
            attrs={'reference_date': ref_date, 'secondary_date': sec_date, 'frame_id': 1},
            coords=coords,
        )
        return da

    xrs = [
        create_data_array([1.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 2)),
        create_data_array([5.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 3)),
        create_data_array([-1.0, 0.0], datetime(1, 1, 3), datetime(1, 1, 4)),
        create_data_array([7.0, 0.0], datetime(1, 1, 3), datetime(1, 1, 5)),
        create_data_array([-3.0, 1.0], datetime(1, 1, 5), datetime(1, 1, 6)),
    ]
    expected = [
        create_data_array([0.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 1)),
        create_data_array([1.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 2)),
        create_data_array([5.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 3)),
        create_data_array([4.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 4)),
        create_data_array([12.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 5)),
        create_data_array([9.0, 1.0], datetime(1, 1, 1), datetime(1, 1, 6)),
    ]
    prep_stack.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 1))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        create_data_array([1.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 2)),
        create_data_array([5.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 3)),
        create_data_array([-1.0, 0.0], datetime(1, 1, 3), datetime(1, 1, 4)),
        create_data_array([7.0, 0.0], datetime(1, 1, 3), datetime(1, 1, 5)),
        create_data_array([-3.0, 1.0], datetime(1, 1, 5), datetime(1, 1, 6)),
    ]
    expected = [
        create_data_array([0.0, 0.0], datetime(1, 1, 2), datetime(1, 1, 2)),
        create_data_array([4.0, 0.0], datetime(1, 1, 2), datetime(1, 1, 3)),
        create_data_array([3.0, 0.0], datetime(1, 1, 2), datetime(1, 1, 4)),
        create_data_array([11.0, 0.0], datetime(1, 1, 2), datetime(1, 1, 5)),
        create_data_array([8.0, 1.0], datetime(1, 1, 2), datetime(1, 1, 6)),
    ]

    prep_stack.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 1, 12))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [create_data_array([20.0, -5.0], datetime(1, 1, 1), datetime(1, 1, 2))]
    expected = [
        create_data_array([0.0, 0.0], datetime(1, 1, 1), datetime(1, 1, 1)),
        create_data_array([20.0, -5.0], datetime(1, 1, 1), datetime(1, 1, 2)),
    ]
    prep_stack.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 1))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        create_data_array([17.0, 3.0], datetime(1, 1, 10), datetime(1, 1, 20)),
        create_data_array([21.0, -5.0], datetime(1, 1, 10), datetime(1, 1, 30)),
    ]
    expected = [
        create_data_array([0.0, 0.0], datetime(1, 1, 20), datetime(1, 1, 20)),
        create_data_array([4.0, -8.0], datetime(1, 1, 20), datetime(1, 1, 30)),
    ]
    prep_stack.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 19))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        create_data_array([17.0, 3.0], datetime(1, 1, 10), datetime(1, 1, 20)),
        create_data_array([21.0, -5.0], datetime(1, 1, 10), datetime(1, 1, 30)),
    ]
    expected = [
        create_data_array([0.0, 0.0], datetime(1, 1, 10), datetime(1, 1, 10)),
        create_data_array([17.0, 3.0], datetime(1, 1, 10), datetime(1, 1, 20)),
        create_data_array([21.0, -5.0], datetime(1, 1, 10), datetime(1, 1, 30)),
    ]
    prep_stack.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 9))
    assert all(a.identical(b) for a, b in zip(xrs, expected))


def test_check_connected_network():
    prep_stack.check_connected_network([])

    prep_stack.check_connected_network(
        [
            xr.DataArray(attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 10)}),
            xr.DataArray(attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 20)}),
        ]
    )

    prep_stack.check_connected_network(
        [
            xr.DataArray(attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 10)}),
            xr.DataArray(attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 20)}),
            xr.DataArray(attrs={'reference_date': datetime(1, 1, 20), 'secondary_date': datetime(1, 1, 30)}),
        ]
    )

    with pytest.raises(ValueError):
        prep_stack.check_connected_network(
            [
                xr.DataArray(attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 10)}),
                xr.DataArray(attrs={'reference_date': datetime(1, 1, 20), 'secondary_date': datetime(1, 1, 30)}),
            ]
        )

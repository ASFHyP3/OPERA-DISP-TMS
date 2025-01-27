from datetime import datetime
from unittest import mock

import numpy as np
import xarray as xr

from opera_disp_tms import create_measurement_geotiff as geo


def test_create_product_name():
    begin_date = datetime(2021, 1, 1)
    end_date = datetime(2021, 1, 2)
    product_name = geo.create_geotiff_name('displacement', 123, begin_date, end_date)
    assert product_name == 'displacement_00123_20210101_20210102.tif'

    begin_date = datetime(2020, 2, 3)
    end_date = datetime(2022, 11, 12)
    product_name = geo.create_geotiff_name('secant_velocity', 54321, begin_date, end_date)
    assert product_name == 'secant_velocity_54321_20200203_20221112.tif'


def test_get_years_since_start():
    datetimes = [datetime(2020, 1, 1), datetime(2020, 1, 2), datetime(2020, 1, 3)]
    assert isinstance(geo.get_years_since_start(datetimes), np.ndarray)
    assert np.allclose(geo.get_years_since_start(datetimes), [0.0, 1 / 365.25, 2 / 365.25])

    datetimes = [datetime(2020, 1, 1), datetime(2020, 1, 1), datetime(2020, 1, 1)]
    assert np.allclose(geo.get_years_since_start(datetimes), [0.0, 0.0, 0.0])

    datetimes = [datetime(2020, 1, 1), datetime(2021, 1, 1), datetime(2022, 1, 1)]
    assert np.allclose(geo.get_years_since_start(datetimes).round(2), [0.0, 1.0, 2.0])


def test_linear_regression_leastsquares():
    x = np.arange(10, dtype='float64')
    y = np.arange(10, dtype='float64')
    slope, intercept = geo.linear_regression_leastsquares(x, y)
    assert np.isclose(slope, 1.0, atol=1e-6)
    assert np.isclose(intercept, 0.0, atol=1e-6)

    slope, intercept = geo.linear_regression_leastsquares(x * -1, y + 2)
    assert np.isclose(slope, -1.0, atol=1e-6)
    assert np.isclose(intercept, 2.0, atol=1e-6)

    slope, intercept = geo.linear_regression_leastsquares(x[0:2] * 1e-6, y[0:2] * 1e-6)
    assert np.isclose(slope, 1.0, atol=1e-6)
    assert np.isclose(intercept, 0.0, atol=1e-6)

    x_1 = np.ones(10, dtype='float64')
    slope, intercept = geo.linear_regression_leastsquares(x_1, y)
    assert np.isnan(slope)
    assert np.isnan(intercept)

    x_nan = x.copy()
    x_nan[4] = np.nan
    slope, intercept = geo.linear_regression_leastsquares(x_nan, y)
    assert np.isclose(slope, 1.0, atol=1e-6)
    assert np.isclose(intercept, 0.0, atol=1e-6)


def test_parallel_linear_regression():
    y_col = np.arange(3, dtype='float64')
    y = np.ones((3, 5, 5), dtype='float64') * -1
    indexes = np.arange(5)
    for i in indexes:
        for j in indexes:
            y[:, i, j] = y_col
    x = np.arange(3, dtype='float64')
    slope = geo.parallel_linear_regression(x, y)
    assert np.all(np.isclose(slope, 1.0, atol=1e-6))


def test_get_data():
    def create_data_array(data, ref_date, sec_date):
        da = xr.DataArray(
            data=data,
            attrs={
                'reference_date': ref_date,
                'secondary_date': sec_date,
                'frame_id': 1,
            },
            coords={
                'x': [1, 2],
                'y': [1, 2],
                'spatial_ref': 'foo',
            },
            dims=['y', 'x'],
        )
        return da

    stack = [
        create_data_array([[0.0, 0.0], [0.0, 0.0]], datetime(1, 1, 1), datetime(1, 1, 1)),
        create_data_array([[8.0, 0.0], [0.0, 0.0]], datetime(1, 1, 1), datetime(1, 1, 5)),
        create_data_array([[3.0, 0.0], [0.0, 0.0]], datetime(1, 1, 1), datetime(1, 1, 6)),
    ]

    with mock.patch('opera_disp_tms.prep_stack.load_sw_disp_stack', return_value=stack) as mock_load_sw_disp_stack:
        expected = xr.DataArray(
            data=[[3.0, 0.0], [0.0, 0.0]],
            attrs={
                'reference_date': datetime(1, 1, 1),
                'secondary_date': datetime(1, 1, 6),
                'frame_id': 1,
            },
            coords={
                'x': [1, 2],
                'y': [1, 2],
                'spatial_ref': 'foo',
            },
            dims=['y', 'x'],
        )
        actual = geo.get_data('displacement', 1, datetime(1, 1, 1), datetime(1, 1, 2))
        xr.testing.assert_identical(actual, expected)

        expected = xr.DataArray(
            data=[[219.15, 0.0], [0.0, 0.0]],
            attrs={
                'reference_date': datetime(1, 1, 1),
                'secondary_date': datetime(1, 1, 6),
                'frame_id': 1,
            },
            coords={
                'x': [1, 2],
                'y': [1, 2],
                'spatial_ref': 'foo',
            },
            dims=['y', 'x'],
        )
        actual = geo.get_data('secant_velocity', 2, datetime(1, 1, 2), datetime(1, 1, 3))
        xr.testing.assert_identical(actual, expected)

        expected = xr.DataArray(
            data=[[365.25, 0.0], [0.0, 0.0]],
            attrs={
                'reference_date': datetime(1, 1, 1),
                'secondary_date': datetime(1, 1, 6),
                'frame_id': 1,
            },
            coords={
                'x': [1, 2],
                'y': [1, 2],
                'spatial_ref': 'foo',
            },
            dims=['y', 'x'],
        )
        actual = geo.get_data('velocity', 3, datetime(1, 1, 3), datetime(1, 1, 4))
        xr.testing.assert_identical(actual, expected)

        mock_load_sw_disp_stack.assert_has_calls(
            [
                mock.call.load_sw_disp_stack(1, datetime(1, 1, 1), datetime(1, 1, 2), 'spanning'),
                mock.call.load_sw_disp_stack(2, datetime(1, 1, 2), datetime(1, 1, 3), 'spanning'),
                mock.call.load_sw_disp_stack(3, datetime(1, 1, 3), datetime(1, 1, 4), 'spanning'),
            ]
        )

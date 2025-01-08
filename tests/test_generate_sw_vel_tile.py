from datetime import datetime

import numpy as np
import xarray as xr

from opera_disp_tms import generate_sw_vel_tile as sw_vel


def test_get_years_since_start():
    datetimes = [datetime(2020, 1, 1), datetime(2020, 1, 2), datetime(2020, 1, 3)]
    assert isinstance(sw_vel.get_years_since_start(datetimes), np.ndarray)
    assert np.allclose(sw_vel.get_years_since_start(datetimes), [0.0, 1 / 365.25, 2 / 365.25])

    datetimes = [datetime(2020, 1, 1), datetime(2020, 1, 1), datetime(2020, 1, 1)]
    assert np.allclose(sw_vel.get_years_since_start(datetimes), [0.0, 0.0, 0.0])

    datetimes = [datetime(2020, 1, 1), datetime(2021, 1, 1), datetime(2022, 1, 1)]
    assert np.allclose(sw_vel.get_years_since_start(datetimes).round(2), [0.0, 1.0, 2.0])


def test_linear_regression_leastsquares():
    x = np.arange(10, dtype='float64')
    y = np.arange(10, dtype='float64')
    slope, intercept = sw_vel.linear_regression_leastsquares(x, y)
    assert np.isclose(slope, 1.0, atol=1e-6)
    assert np.isclose(intercept, 0.0, atol=1e-6)

    slope, intercept = sw_vel.linear_regression_leastsquares(x * -1, y + 2)
    assert np.isclose(slope, -1.0, atol=1e-6)
    assert np.isclose(intercept, 2.0, atol=1e-6)

    slope, intercept = sw_vel.linear_regression_leastsquares(x[0:2] * 1e-6, y[0:2] * 1e-6)
    assert np.isclose(slope, 1.0, atol=1e-6)
    assert np.isclose(intercept, 0.0, atol=1e-6)

    x_1 = np.ones(10, dtype='float64')
    slope, intercept = sw_vel.linear_regression_leastsquares(x_1, y)
    assert np.isnan(slope)
    assert np.isnan(intercept)

    x_nan = x.copy()
    x_nan[4] = np.nan
    slope, intercept = sw_vel.linear_regression_leastsquares(x_nan, y)
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
    slope = sw_vel.parallel_linear_regression(x, y)
    assert np.all(np.isclose(slope, 1.0, atol=1e-6))


def test_align_to_common_reference_date():
    xrs = [
        xr.DataArray(data=[1.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 2)}),
        xr.DataArray(data=[5.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 3)}),
        xr.DataArray(
            data=[-1.0, 0.0], attrs={'reference_date': datetime(1, 1, 3), 'secondary_date': datetime(1, 1, 4)}
        ),
        xr.DataArray(data=[7.0, 0.0], attrs={'reference_date': datetime(1, 1, 3), 'secondary_date': datetime(1, 1, 5)}),
        xr.DataArray(
            data=[-3.0, 1.0], attrs={'reference_date': datetime(1, 1, 5), 'secondary_date': datetime(1, 1, 6)}
        ),
    ]
    expected = [
        xr.DataArray(data=[0.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 1)}),
        xr.DataArray(data=[1.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 2)}),
        xr.DataArray(data=[5.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 3)}),
        xr.DataArray(data=[4.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 4)}),
        xr.DataArray(
            data=[12.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 5)}
        ),
        xr.DataArray(data=[9.0, 1.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 6)}),
    ]
    sw_vel.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 1))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        xr.DataArray(data=[1.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 2)}),
        xr.DataArray(data=[5.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 3)}),
        xr.DataArray(
            data=[-1.0, 0.0], attrs={'reference_date': datetime(1, 1, 3), 'secondary_date': datetime(1, 1, 4)}
        ),
        xr.DataArray(data=[7.0, 0.0], attrs={'reference_date': datetime(1, 1, 3), 'secondary_date': datetime(1, 1, 5)}),
        xr.DataArray(
            data=[-3.0, 1.0], attrs={'reference_date': datetime(1, 1, 5), 'secondary_date': datetime(1, 1, 6)}
        ),
    ]
    expected = [
        xr.DataArray(data=[0.0, 0.0], attrs={'reference_date': datetime(1, 1, 2), 'secondary_date': datetime(1, 1, 2)}),
        xr.DataArray(data=[4.0, 0.0], attrs={'reference_date': datetime(1, 1, 2), 'secondary_date': datetime(1, 1, 3)}),
        xr.DataArray(data=[3.0, 0.0], attrs={'reference_date': datetime(1, 1, 2), 'secondary_date': datetime(1, 1, 4)}),
        xr.DataArray(
            data=[11.0, 0.0], attrs={'reference_date': datetime(1, 1, 2), 'secondary_date': datetime(1, 1, 5)}
        ),
        xr.DataArray(data=[8.0, 1.0], attrs={'reference_date': datetime(1, 1, 2), 'secondary_date': datetime(1, 1, 6)}),
    ]
    sw_vel.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 1, 12))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        xr.DataArray(
            data=[20.0, -5.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 2)}
        ),
    ]
    expected = [
        xr.DataArray(data=[0.0, 0.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 1)}),
        xr.DataArray(
            data=[20.0, -5.0], attrs={'reference_date': datetime(1, 1, 1), 'secondary_date': datetime(1, 1, 2)}
        ),
    ]
    sw_vel.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 1))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        xr.DataArray(
            data=[17.0, 3.0], attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 20)}
        ),
        xr.DataArray(
            data=[21.0, -5.0], attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 30)}
        ),
    ]
    expected = [
        xr.DataArray(
            data=[0.0, 0.0], attrs={'reference_date': datetime(1, 1, 20), 'secondary_date': datetime(1, 1, 20)}
        ),
        xr.DataArray(
            data=[4.0, -8.0], attrs={'reference_date': datetime(1, 1, 20), 'secondary_date': datetime(1, 1, 30)}
        ),
    ]
    sw_vel.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 19))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

    xrs = [
        xr.DataArray(
            data=[17.0, 3.0], attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 20)}
        ),
        xr.DataArray(
            data=[21.0, -5.0], attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 30)}
        ),
    ]
    expected = [
        xr.DataArray(
            data=[0.0, 0.0], attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 10)}
        ),
        xr.DataArray(
            data=[17.0, 3.0], attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 20)}
        ),
        xr.DataArray(
            data=[21.0, -5.0], attrs={'reference_date': datetime(1, 1, 10), 'secondary_date': datetime(1, 1, 30)}
        ),
    ]
    sw_vel.align_to_common_reference_date(xrs, start_date=datetime(1, 1, 9))
    assert all(a.identical(b) for a, b in zip(xrs, expected))

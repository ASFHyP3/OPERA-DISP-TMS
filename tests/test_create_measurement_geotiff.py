from datetime import datetime

import numpy as np

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

import numpy as np

from opera_disp_tms import generate_sw_vel_tile as sw_vel


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
    x_col = np.arange(3, dtype='float64')
    x = np.ones((3, 5, 5), dtype='float64') * -1
    indexes = np.arange(5)
    for i in indexes:
        for j in indexes:
            x[:, i, j] = x_col
    y = np.arange(3, dtype='float64')
    slope = sw_vel.parallel_linear_regression(x, y)
    assert np.all(np.isclose(slope, 1.0, atol=1e-6))

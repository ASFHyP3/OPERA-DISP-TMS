import argparse
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import xarray as xr
from numba import njit, prange
from osgeo import gdal

from opera_disp_tms.prep_stack import load_sw_disp_stack
from opera_disp_tms import utils


gdal.UseExceptions()


@njit
def linear_regression_leastsquares(x: np.ndarray, y: np.ndarray) -> tuple:
    """Based on the scipy.stats.linregress implementation:
    https://github.com/scipy/scipy/blob/v1.14.1/scipy/stats/_stats_py.py#L10752-L10947

    Args:
        x: The independent variable as a 1D numpy array
        y: The dependent variable as a 1D numpy array

    Returns:
        tuple: The slope and intercept of the linear regression
    """
    non_nan_indices = np.where(~np.isnan(x))
    x = x[non_nan_indices]
    y = y[non_nan_indices]

    if len(x) < 2:
        return np.nan, np.nan

    if np.amax(x) == np.amin(x) and len(x) > 1:
        return np.nan, np.nan

    xmean = np.mean(x)
    ymean = np.mean(y)
    ssxm, ssxym, _, ssym = np.cov(x, y, bias=True).flat
    slope = ssxym / ssxm
    intercept = ymean - slope * xmean
    return slope, intercept


@njit(parallel=True)
def parallel_linear_regression(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Run linear regresions in parallel for each pixel in the x array

    Args:
        x: A 1D array of independent variables (i.e., time steps)
        y: A 3D array of dependent variables with dimensions (time, y, x)
    """
    n, m, p = y.shape
    slope_array = np.zeros((m, p))
    for i in prange(m):
        for j in prange(p):
            slope, intercept = linear_regression_leastsquares(x, y[:, i, j].copy())
            slope_array[i, j] = slope
    return slope_array


def get_years_since_start(datetimes: List[datetime]) -> np.ndarray:
    """Get the number of years since the earliest date as an array of floats.
    Order of the datetimes is preserved.

    Args:
        datetimes: A list of datetime objects

    Returns:
        np.ndarray: The number of years since the earliest date as a list of floats
    """
    start = min(datetimes)
    yrs_since_start = np.array([(date - start).days / 365.25 for date in datetimes])
    return yrs_since_start


def create_sw_vel_tile(frame_id: int, begin_date: datetime, end_date: datetime, secant: bool = True) -> Path:
    if secant:
        product_name = utils.create_tile_name(frame_id, begin_date, end_date, 'secant-velocity')
    else:
        product_name = utils.create_tile_name(frame_id, begin_date, end_date, 'velocity')
    product_path = Path.cwd() / product_name

    strategy = 'spanning' if secant else 'all'
    granule_xrs = load_sw_disp_stack(frame_id, begin_date, end_date, strategy)
    if strategy == 'secant':
        granule_xrs = [granule_xrs[0], granule_xrs[-1]]
    cube = xr.concat(granule_xrs, dim='years_since_start')

    years_since_start = get_years_since_start([g.attrs['secondary_date'] for g in granule_xrs])
    cube = cube.assign_coords(years_since_start=years_since_start)
    new_coords = {'x': cube.x, 'y': cube.y, 'spatial_ref': cube.spatial_ref}

    # Using xarray's polyfit is 13x slower when running a regression for 44 time steps
    slope = parallel_linear_regression(cube.years_since_start.data.astype('float64'), cube.data.astype('float64'))
    slope_da = xr.DataArray(slope, dims=('y', 'x'), coords=new_coords)
    velocity = xr.Dataset({'velocity': slope_da}, new_coords)
    velocity.attrs = cube.attrs


    velocity.rio.write_nodata(np.nan, inplace=True)
    velocity = velocity.rio.reproject('EPSG:3857')
    velocity.rio.to_raster(product_path.name)
    return product_path


def main():
    """CLI entry point
    Example:
    generate_sw_disp_tile METADATA_ASCENDING_N42W124.tif 20160101 20190101
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('frame_id', type=int)
    parser.add_argument(
        'begin_date', type=str, help='Start of secondary date search range to generate tile for (e.g., 20211231)'
    )
    parser.add_argument(
        'end_date', type=str, help='End of secondary date search range to generate tile for (e.g., 20211231)'
    )
    parser.add_argument(
        '--full', action='store_false', help='Use a full linear fit instead of a secant fit (first/last date only)'
    )

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    create_sw_vel_tile(args.frame_id, args.begin_date, args.end_date, secant=args.full)


if __name__ == '__main__':
    main()

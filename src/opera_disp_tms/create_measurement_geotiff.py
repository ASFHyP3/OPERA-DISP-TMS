import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import xarray as xr
from numba import njit, prange
from osgeo import gdal

from opera_disp_tms import prep_stack
from opera_disp_tms.utils import upload_file_to_s3


gdal.UseExceptions()


def create_geotiff_name(measurement_type: str, frame_id: int, begin_date: datetime, end_date: datetime) -> str:
    """Create a product name for a geotiff
    Takes the form: MEAUREMENTTYPE_FRAMEID_YYYYMMDD_YYYYMMDD.tif
    e.g.: displacement_012345_20140101_20260101.tif

    Args:
        measurement_type: The data measurement type of the geotiff
        frame_id: The frame id of the geotiff
        begin_date: Start of secondary date search range to generate geotiff for
        end_date: End of secondary date search range to generate geotiff for
    """
    date_fmt = '%Y%m%d'
    begin_date_str = datetime.strftime(begin_date, date_fmt)
    end_date_str = datetime.strftime(end_date, date_fmt)
    name = f'{measurement_type}_{frame_id:05}_{begin_date_str}_{end_date_str}.tif'
    return name


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


def get_years_since_start(datetimes: list[datetime]) -> np.ndarray:
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


def compute_measurement(measurement_type: str, stack: list[xr.DataArray]) -> xr.DataArray:
    if measurement_type not in ['displacement', 'velocity', 'secant_velocity']:
        raise ValueError(f'Invalid measurement type: {measurement_type}')

    if measurement_type == 'displacement':
        return stack[-1]

    if measurement_type == 'secant_velocity':
        stack = [stack[0], stack[-1]]

    cube = xr.concat(stack, dim='years_since_start')
    years_since_start = get_years_since_start([g.attrs['secondary_date'] for g in stack])
    cube = cube.assign_coords(years_since_start=years_since_start)

    # Using xarray's polyfit is 13x slower when running a regression for 44 time steps
    slope = parallel_linear_regression(cube.years_since_start.data.astype('float64'), cube.data.astype('float64'))

    new_coords = {'x': cube.x, 'y': cube.y, 'spatial_ref': cube.spatial_ref}
    slope_da = xr.DataArray(slope, dims=('y', 'x'), coords=new_coords, attrs=stack[-1].attrs)
    return slope_da


def create_measurement_geotiff(measurement_type: str, frame_id: int, begin_date: datetime, end_date: datetime) -> Path:
    stack = prep_stack.load_sw_disp_stack(frame_id, begin_date, end_date, 'spanning')
    data = compute_measurement(measurement_type, stack)

    data.rio.write_nodata(np.nan, inplace=True)
    data = data.rio.reproject('EPSG:3857')

    product_name = create_geotiff_name(measurement_type, frame_id, begin_date, end_date)
    product_path = Path.cwd() / product_name
    data.rio.to_raster(product_path.name)

    return product_path


def make_parser():
    parser = argparse.ArgumentParser(description='Create a short wavelength displacement or velocity geotiff')

    def frame_type(frame):
        frame = int(frame)

        if not (1 <= frame <= 46986):
            parser.error(f'Value {frame} must be between 1 and 46986')

        return frame

    parser.add_argument('frame_id', type=frame_type, help='Frame id of the OPERA DISP granule stack to process')
    parser.add_argument(
        'measurement_type',
        type=str,
        choices=['displacement', 'secant_velocity', 'velocity'],
        help='Data measurement to compute',
    )
    parser.add_argument(
        'begin_date', type=str, help='Start of secondary date search range to generate tile for (e.g., 20211231)'
    )
    parser.add_argument(
        'end_date', type=str, help='End of secondary date search range to generate tile for (e.g., 20211231)'
    )

    parser.add_argument('--bucket', help='AWS S3 bucket HyP3 for upload the final products')
    parser.add_argument('--bucket-prefix', default='', help='Add a bucket prefix to products')

    return parser


def main():
    """CLI entry point
    Example:
    create_measurement_geotiff displacement 11114 20140101 20260101
    """
    parser = make_parser()

    args = parser.parse_args()
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    measurement_geotiff_path = create_measurement_geotiff(
        args.measurement_type, args.frame_id, args.begin_date, args.end_date
    )

    if args.bucket:
        upload_file_to_s3(Path(measurement_geotiff_path), args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

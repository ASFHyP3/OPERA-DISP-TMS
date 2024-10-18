import argparse
from datetime import datetime
from pathlib import Path

import numba
import numpy as np
import xarray as xr
from osgeo import gdal
from rasterio.transform import Affine

from opera_disp_tms import generate_sw_disp_tile as sw_disp
from opera_disp_tms.utils import create_buffered_bbox, get_raster_as_numpy


gdal.UseExceptions()


def get_years_since_start(datetimes):
    start = min(datetimes)
    yrs_since_start = [(date - start).days / 365.25 for date in datetimes]
    return yrs_since_start


# def linear_regression_np(data, x):
#     n, m, p = data.shape
#     slope = np.zeros((m, p))
#     intercept = np.zeros((m, p))
#
#     X = np.vstack([x, np.ones_like(x)]).T
#
#     for i in range(m):
#         for j in range(p):
#             y = data[:, i, j]
#             slope[i, j], intercept[i, j] = np.linalg.lstsq(X, y, rcond=None)[0]
#
#     return slope, intercept
#
#
# @numba.njit
# def linear_regression_leastsquares_bad(X, y):
#     n = len(X)
#     X_mean = np.mean(X)
#     y_mean = np.mean(y)
#
#     numerator = 0.0
#     denominator = 0.0
#
#     for i in range(n):
#         numerator += (X[i] - X_mean) * (y[i] - y_mean)
#         denominator += (X[i] - X_mean) ** 2
#
#     if denominator == 0:
#         return np.nan, np.nan
#
#     slope = numerator / denominator
#     intercept = y_mean - slope * X_mean
#     return slope, intercept


# @numba.njit
# def linear_regression_leastsquares(X, y):
#     if np.all(np.isnan(X)):
#         return np.nan, np.nan
#
#     if np.all(np.isclose(y, y[0], atol=1e-6)):
#         return 0.0, y[0]
#
#     X_b = np.zeros((X.shape[0], 2), dtype=X.dtype)
#     X_b[:, 0] = X
#     X_b[:, 1] = np.ones_like(X)
#
#     step1 = np.dot(X_b.T, X_b)
#     step2 = np.linalg.inv(step1)
#     step3 = np.dot(step2, X_b.T)
#     theta = np.dot(step3, y)
#     slope, intercept = theta[0], theta[1]
#     return slope, intercept


# @numba.njit
# def linear_regression_leastsquares(X, y):
#     if np.all(np.isnan(X)):
#         return np.nan, np.nan
#
#     if np.all(np.isclose(y, y[0], atol=1e-6)):
#         return 0.0, y[0]
#
#     X_b = np.zeros((X.shape[0], 2), dtype=X.dtype)
#     X_b[:, 0] = X
#     X_b[:, 1] = np.ones_like(X)
#     slope, intercept = np.linalg.lstsq(X_b, y, rcond=None)[0]
#     return slope, intercept


@numba.njit
def linear_regression_leastsquares(x, y):
    """From: https://www4.stat.ncsu.edu/%7Edickey/courses/st512/pdf_notes/Formulas.pdf"""
    if np.all(np.isnan(x)):
        return np.nan, np.nan

    n = len(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    x_square_sum = np.sum(x**2)
    sum_cross = np.sum(x * y)
    x_correction = x_square_sum - (n * x_mean**2)
    if np.isclose(x_correction, 0.0, atol=1e-6):
        return np.nan, np.nan
    xy_correction = sum_cross - (n * x_mean * y_mean)
    slope = xy_correction / x_correction
    intercept = y_mean - (slope * x_mean)
    return slope, intercept


@numba.njit(parallel=True)
def parallel_linear_regression(X, y):
    n, m, p = X.shape
    slope = np.zeros((m, p))
    intercept = np.zeros((m, p))
    for i in numba.prange(m):
        for j in numba.prange(p):
            slope[i, j], intercept[i, j] = linear_regression_leastsquares(X[:, i, j].copy(), y)
    return slope, intercept


def add_velocity_data_to_array(granules, frame, geotransform, frame_map_array, out_array):
    bbox = create_buffered_bbox(geotransform.to_gdal(), frame_map_array.shape, 90)  # EPSG:3857 is in meters
    granule_xrs = [sw_disp.load_sw_disp_granule(x, bbox, frame) for x in granules]
    cube = xr.concat(granule_xrs, dim='years_since_start')

    years_since_start = get_years_since_start([g.attrs['secondary_date'] for g in granule_xrs])
    cube = cube.assign_coords(years_since_start=years_since_start)
    non_nan_count = cube.count(dim='years_since_start')
    cube = cube.where(non_nan_count >= 2, np.nan)

    cube_array = cube.data * 1_000_000  # convert to um
    slope, intercept = parallel_linear_regression(cube_array, cube.years_since_start.data.astype('float64'))
    new_coords = {'x': cube.x, 'y': cube.y, 'spatial_ref': cube.spatial_ref}
    slope_da = xr.DataArray(slope, dims=('y', 'x'), coords=new_coords)
    velocity = xr.Dataset({'velocity': slope_da * 10_000, 'count': non_nan_count}, new_coords)
    velocity.attrs = cube.attrs

    # cube *= 1_000_000  # convert to um/yr
    # linear_fit = cube.polyfit(dim='years_since_start', deg=1)
    # slope_da = linear_fit.polyfit_coefficients.sel(degree=1) / 10_000 # convert to cm/yr
    # velocity = xr.Dataset({'velocity': slope_da, 'count': non_nan_count})
    # velocity.attrs = cube.attrs

    velocity_reproj = velocity['velocity'].rio.reproject(
        'EPSG:3857', transform=geotransform, shape=frame_map_array.shape
    )
    frame_locations = frame_map_array == velocity.attrs['frame_id']
    out_array[frame_locations] = velocity_reproj.data[frame_locations].astype(float)
    return out_array


def create_sw_vel_tile(metadata_path: Path, begin_date: datetime, end_date: datetime, minmax: bool = True):
    if not metadata_path.exists():
        raise FileNotFoundError(f'{metadata_path} does not exist')
    if begin_date > end_date:
        raise ValueError('Begin date must be before end date')

    product_name = sw_disp.create_product_name(metadata_path.name, begin_date, end_date, 'SW_VELOCITY')
    product_path = Path.cwd() / product_name
    print(f'Generating tile {product_name}')

    frames = sw_disp.frames_from_metadata(metadata_path)
    strategy = 'minmax' if minmax else 'all'
    needed_granules = sw_disp.find_needed_granules(list(frames.keys()), begin_date, end_date, strategy=strategy)
    len_str = [f'    {frame_id}: {len(needed_granules[frame_id])}' for frame_id in needed_granules]
    print('\n'.join(['N granules:'] + len_str))

    frame_map, geotransform = get_raster_as_numpy(metadata_path)
    geotransform = Affine.from_gdal(*geotransform)
    sw_vel = np.full(frame_map.shape, np.nan, dtype=float)
    for frame_id, granules in needed_granules.items():
        frame = frames[frame_id]
        sw_vel = add_velocity_data_to_array(granules, frame, geotransform, frame_map, sw_vel)

    gdal.Translate(str(product_path), str(metadata_path), outputType=gdal.GDT_Float32, format='GTiff')
    ds = gdal.Open(str(product_path), gdal.GA_Update)
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(np.nan)
    band.WriteArray(sw_vel)
    ds.SetMetadata(ds.GetMetadata())
    ds.FlushCache()
    ds = None
    print('Done!')
    return product_path


def main():
    """CLI entry point
    Example:
    generate_sw_disp_tile METADATA_ASCENDING_N42W124.tif 20160101 20190101
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('metadata_path', type=str, help='Path to the metadata tile')
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

    create_sw_vel_tile(args.metadata_path, args.begin_date, args.end_date, minmax=args.full)


if __name__ == '__main__':
    main()

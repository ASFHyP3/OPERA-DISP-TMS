import argparse
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import numpy as np
import xarray as xr
from numba import njit, prange
from osgeo import gdal
from rasterio.transform import Affine

from opera_disp_tms import generate_sw_disp_tile as sw_disp
from opera_disp_tms.search import Granule
from opera_disp_tms.utils import create_buffered_bbox, create_tile_name, get_raster_as_numpy


gdal.UseExceptions()


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


def add_velocity_data_to_array(
    granules: Iterable[Granule],
    geotransform: Affine,
    frame_map_array: np.ndarray,
    out_array: np.ndarray,
) -> np.ndarray:
    """Create and add velocity data to an array using granules source from a single frame.

    Args:
        granules: A list of granule objects
        frame: The frame metadata
        geotransform: The geotransform of the frame
        frame_map_array: The frame map as a numpy array
        out_array: The array to add the velocity data to

    Returns:
        np.ndarray: The updated array
    """
    bbox = create_buffered_bbox(geotransform.to_gdal(), frame_map_array.shape, 90)  # EPSG:3857 is in meters
    granule_xrs = [sw_disp.load_sw_disp_granule(x, bbox) for x in granules]
    cube = xr.concat(granule_xrs, dim='years_since_start')

    years_since_start = get_years_since_start([g.attrs['secondary_date'] for g in granule_xrs])
    cube = cube.assign_coords(years_since_start=years_since_start)
    new_coords = {'x': cube.x, 'y': cube.y, 'spatial_ref': cube.spatial_ref}

    # Using xarray's polyfit is 13x slower when running a regression for 44 time steps
    slope = parallel_linear_regression(cube.years_since_start.data.astype('float64'), cube.data.astype('float64'))
    slope_da = xr.DataArray(slope, dims=('y', 'x'), coords=new_coords)
    velocity = xr.Dataset({'velocity': slope_da}, new_coords)
    velocity.attrs = cube.attrs

    velocity_reproj = velocity['velocity'].rio.reproject(
        'EPSG:3857', transform=geotransform, shape=frame_map_array.shape
    )
    frame_locations = frame_map_array == velocity.attrs['frame_id']
    out_array[frame_locations] = velocity_reproj.data[frame_locations].astype(float)
    return out_array


def create_sw_vel_tile(metadata_path: Path, begin_date: datetime, end_date: datetime, minmax: bool = True) -> Path:
    if not metadata_path.exists():
        raise FileNotFoundError(f'{metadata_path} does not exist')
    if begin_date > end_date:
        raise ValueError('Begin date must be before end date')

    product_name = create_tile_name(metadata_path.name, begin_date, end_date, 'SW_VELOCITY')
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
    for granules in needed_granules.values():
        sw_vel = add_velocity_data_to_array(granules, geotransform, frame_map, sw_vel)

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

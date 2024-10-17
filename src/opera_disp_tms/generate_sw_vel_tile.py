import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import xarray as xr
from dask.distributed import LocalCluster
from osgeo import gdal
from rasterio.transform import Affine

from opera_disp_tms import generate_sw_disp_tile as sw_disp
from opera_disp_tms.utils import create_buffered_bbox, get_raster_as_numpy


gdal.UseExceptions()


def get_years_since_start(datetimes):
    start = min(datetimes)
    yrs_since_start = [(date - start).days / 365.25 for date in datetimes]
    return yrs_since_start


def add_velocity_data_to_array(granules, frame, geotransform, frame_map_array, out_array):
    bbox = create_buffered_bbox(geotransform.to_gdal(), frame_map_array.shape, 90)  # EPSG:3857 is in meters
    # TODO: Multithred to speed up
    granule_xrs = [sw_disp.load_sw_disp_granule(x, bbox, frame) for x in granules]
    cube = xr.concat(granule_xrs, dim='years_since_start')
    # ensures output units are m/yr
    years_since_start = get_years_since_start([g.attrs['secondary_date'] for g in granule_xrs])
    cube = cube.assign_coords(years_since_start=years_since_start)
    del cube.attrs['secondary_date']
    non_nan_count = cube.count(dim='years_since_start')
    cube = cube.where(non_nan_count >= 2, np.nan)

    cluster = LocalCluster()
    client = cluster.get_client()
    cube = cube.chunk({'x': 500, 'y': 500, 'years_since_start': -1})
    linear_fit = cube.polyfit(dim='years_since_start', deg=1)
    linear_fit = linear_fit.compute(client=client)
    client.close()

    # multiplying by 100 converts to cm/yr
    velocity = xr.Dataset({'velocity': linear_fit.polyfit_coefficients.sel(degree=1) * 100, 'count': non_nan_count})
    velocity.attrs = cube.attrs

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

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    create_sw_vel_tile(args.metadata_path, args.begin_date, args.end_date)


if __name__ == '__main__':
    main()

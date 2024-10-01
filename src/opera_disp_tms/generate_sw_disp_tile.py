import argparse
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import xarray as xr
from osgeo import gdal
from rasterio.transform import Affine

from opera_disp_tms.find_california_dataset import find_california_dataset
from opera_disp_tms.utils import (
    open_opera_disp_granule,
    round_to_nearest_day,
    transform_point,
    wkt_from_epsg,
)


gdal.UseExceptions()


DATE_FORMAT = '%Y%m%dT%H%M%SZ'


@dataclass
class Frame:
    frame: int
    reference_date: datetime
    reference_point_array: tuple  # column, row
    reference_point_geo: tuple  # lon, lat


def frames_from_metadata(metadata_path):
    info_dict = gdal.Info(str(metadata_path), options=['-json'])
    frame_metadata = info_dict['metadata']['']
    frame_ids = [int(x) for x in frame_metadata['OPERA_FRAMES'].split(', ')]
    frames = []
    for frame_id in frame_ids:
        ref_date = datetime.strptime(frame_metadata[f'FRAME_{frame_id}_REF_TIME'], DATE_FORMAT)

        ref_point_array = frame_metadata[f'FRAME_{frame_id}_REF_POINT_ARRAY']
        ref_point_array = tuple([int(x) for x in ref_point_array.split(', ')])

        ref_point_geo = frame_metadata[f'FRAME_{frame_id}_REF_POINT_GEO']
        ref_point_geo = tuple([float(x) for x in ref_point_geo.split(', ')])

        frame = Frame(frame_id, ref_date, ref_point_array, ref_point_geo)
        frames.append(frame)
    return frames


def find_needed_granules(frame_ids, begin_date, end_date):
    cali_dataset = find_california_dataset()
    needed_granules = []
    for frame_id in frame_ids:
        granules = [x for x in cali_dataset if x.frame == frame_id]
        granules = [x for x in granules if begin_date <= x.secondary_date <= end_date]
        if not granules:
            warnings.warn(f'No granules found for frame {frame_id} between {begin_date} and {end_date}.')
        else:
            granule = max(granules, key=lambda x: x.secondary_date)
            needed_granules.append(granule)
    return needed_granules


def update_spatiotemporal_reference(in_granule: xr.DataArray, frame: Frame) -> xr.DataArray:
    if in_granule.attrs['frame'] != frame.frame:
        raise ValueError('Granule frame does not match frame metadata')

    if round_to_nearest_day(in_granule.attrs['reference_date']) != round_to_nearest_day(frame.reference_date):
        raise NotImplementedError('Granule reference date does not match frame metadata, this is not yet supported.')

    if in_granule.attrs['reference_point_geo'] != frame.reference_point_geo:
        ref_x, ref_y = transform_point(
            frame.reference_point_geo[0],
            frame.reference_point_geo[1],
            wkt_from_epsg(4326),
            in_granule['spatial_ref'].attrs['crs_wkt'],
        )
        ref_value = in_granule.sel(x=ref_x, y=ref_y, method='nearest').data.item()
        in_granule -= ref_value
        in_granule.attrs['reference_point_array'] = frame.reference_point_array
        in_granule.attrs['reference_point_geo'] = frame.reference_point_geo

    return in_granule


def create_blank_copy_tile(input_path, output_path, dtype='float32'):
    if dtype not in ['int16', 'float32']:
        raise NotImplementedError(f'Dtype {dtype} not implemented')

    ds = gdal.Open(str(input_path))
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()
    data[:] = 0

    if dtype == 'int16':
        data = data.astype(int)
        gdal_dtype = gdal.GDT_Int16
    else:
        data = data.astype(float)
        gdal_dtype = gdal.GDT_Float32

    opts = ['TILED=YES', 'COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS']
    driver = gdal.GetDriverByName('GTiff')
    out_ds = driver.Create(str(output_path), ds.RasterXSize, ds.RasterYSize, 1, gdal_dtype, options=opts)

    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(data)
    out_ds.SetGeoTransform(ds.GetGeoTransform())
    out_ds.SetProjection(ds.GetProjection())

    out_band.FlushCache()
    out_ds = None
    ds = None


def get_frame_map(metadata_path):
    ds = gdal.Open(str(metadata_path))
    band = ds.GetRasterBand(1)
    frame_map = band.ReadAsArray()
    ds = None
    return frame_map


def create_sw_disp_tile(begin_date: datetime, end_date: datetime, metadata_path: Path):
    if not metadata_path.exists():
        raise FileNotFoundError(f'{metadata_path} does not exist')
    if begin_date > end_date:
        raise ValueError('Begin date must be before end date')

    product_path = metadata_path.parent / metadata_path.name.replace('metadata', 'sw_cumul_disp')

    frame_map = get_frame_map(metadata_path)

    create_blank_copy_tile(metadata_path, product_path)
    ds = gdal.Open(str(product_path), gdal.GA_Update)
    band = ds.GetRasterBand(1)
    sw_cumul_disp = band.ReadAsArray()

    transfrom = Affine.from_gdal(*gdal.Open(str(metadata_path)).GetGeoTransform())
    frames = frames_from_metadata(metadata_path)
    frame_ids = [x.frame for x in frames]
    needed_granules = find_needed_granules(frame_ids, begin_date, end_date)
    for granule in needed_granules:
        granule = open_opera_disp_granule(granule.s3_uri, 'short_wavelength_displacement')
        granule_frame = [x for x in frames if x.frame == granule.attrs['frame']][0]
        granule = update_spatiotemporal_reference(granule, granule_frame)
        granule = granule.rio.reproject('EPSG:3857', transform=transfrom, shape=frame_map.shape)
        frame_locations = frame_map == granule.attrs['frame']
        sw_cumul_disp[frame_locations] = granule.data[frame_locations].astype(float)

    band.WriteArray(sw_cumul_disp)
    band.SetNoDataValue(0)
    secondary_dates = {f'FRAME_{x.frame}_SEC_TIME': x.reference_date.strftime(DATE_FORMAT) for x in frames}
    ds.SetMetadata(secondary_dates)
    ds.FlushCache()
    ds = None


def main():
    """CLI entrpypoint
    Example:
    generate_sw_disp_tile metadata_ASCENDING_N37W122_N38W121.tif \
        --begin-date 20160701T000000Z --end-date 20240922T154629Z
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('metadata_path', type=str, help='Path to the metadata GeoTiff file')
    parser.add_argument('--begin-date', type=str, help='Beginning of date range to generate tile for in format: %Y%m%d')
    parser.add_argument('--end-date', type=str, help='End of date range to generate tile for in format: %Y%m%d')

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, DATE_FORMAT)
    args.end_date = datetime.strptime(args.end_date, DATE_FORMAT)

    create_sw_disp_tile(args.begin_date, args.end_date, args.metadata_path)


if __name__ == '__main__':
    main()

import argparse
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr
from osgeo import gdal
from rasterio.transform import Affine

from opera_disp_tms import utils
from opera_disp_tms.find_california_dataset import Granule, find_california_dataset
from opera_disp_tms.s3_xarray import open_opera_disp_granule
from opera_disp_tms.utils import DATE_FORMAT


gdal.UseExceptions()


@dataclass
class Frame:
    """Dataclass for frame metadata"""

    frame: int
    reference_date: datetime
    reference_point_array: tuple  # column, row
    reference_point_geo: tuple  # lon, lat


def frames_from_metadata(metadata_path: Path) -> list[Frame]:
    """Extract frame metadata from a metadata GeoTiff file

    Args:
        metadata_path (Path): Path to the metadata GeoTiff file

    Returns:
        List of frame metadata
    """
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


def find_needed_granules(frame_ids: Iterable[int], begin_date: datetime, end_date: datetime) -> Iterable[Granule]:
    """Find the granules needed to generate a short wavelength displacement tile

    Args:
        frame_ids: The frame ids to generate the tile for
        begin_date: The beginning of the date range to generate the tile for
        end_date: The end of the date range to generate the tile for

    Returns:
        A list of granules needed to generate the tile
    """
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
    """Update the spatiotemporal reference information of a granule to match the frame metadata

    Args:
        in_granule: The granule to update
        frame: The frame metadata to update the granule to

    Returns:
        The updated granule
    """
    if in_granule.attrs['frame'] != frame.frame:
        raise ValueError('Granule frame does not match frame metadata')

    if utils.round_to_day(in_granule.attrs['reference_date']) != utils.round_to_day(frame.reference_date):
        raise NotImplementedError('Granule reference date does not match frame metadata, this is not yet supported.')

    if in_granule.attrs['reference_point_geo'] != frame.reference_point_geo:
        ref_x, ref_y = utils.transform_point(
            frame.reference_point_geo[0],
            frame.reference_point_geo[1],
            utils.wkt_from_epsg(4326),
            in_granule['spatial_ref'].attrs['crs_wkt'],
        )
        ref_value = in_granule.sel(x=ref_x, y=ref_y, method='nearest').data.item()
        in_granule -= ref_value
        in_granule.attrs['reference_point_array'] = frame.reference_point_array
        in_granule.attrs['reference_point_geo'] = frame.reference_point_geo

    return in_granule


def create_blank_copy_tile(input_path: Path, output_path: Path) -> None:
    """Create a blank copy of a GeoTiff file

    Args:
        input_path: Path to the input GeoTiff file
        output_path: Path to the output GeoTiff file
    """
    ds = gdal.Open(str(input_path))
    metadata = ds.GetMetadata()
    transform = ds.GetGeoTransform()
    projection = ds.GetProjection()
    x_size = ds.RasterXSize
    y_size = ds.RasterYSize
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray().astype(float)
    data[:] = np.nan
    ds = None

    driver = gdal.GetDriverByName('GTiff')
    opts = ['TILED=YES', 'COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS']
    out_ds = driver.Create(str(output_path), x_size, y_size, 1, gdal.GDT_Float32, options=opts)

    out_band = out_ds.GetRasterBand(1)
    out_band.SetNoDataValue(np.nan)
    out_band.WriteArray(data)
    out_ds.SetGeoTransform(transform)
    out_ds.SetProjection(projection)
    out_ds.SetMetadata(metadata)

    out_band.FlushCache()
    out_ds = None


def create_product_name(metadata_name: str, begin_date: datetime, end_date: datetime) -> str:
    """Create a product name for a short wavelength cumulative displacement tile
    Takes the form: SW_CUMUL_DISP_YYYYMMDD_YYYYMMDD_ORBIT_BBOX.tif

    Args:
        metadata_name: The name of the metadata file
        begin_date: The beginning of the date range to generate the tile for
        end_date: The end of the date range to generate the tile for
    """
    parts = metadata_name.split('_')[1:]
    date_fmt = '%Y%m%d'
    begin_date = datetime.strftime(begin_date, date_fmt)
    end_date = datetime.strftime(end_date, date_fmt)
    name = '_'.join(['SW_CUMUL_DISP', begin_date, end_date, *parts])
    return name


def create_sw_disp_tile(metadata_path: Path, begin_date: datetime, end_date: datetime) -> Path:
    """Create a short wavelength cumulative displacement tile

    Args:
        metadata_path: Path to the metadata GeoTiff file
        begin_date: The beginning of the date range to generate the tile for
        end_date: The end of the date range to generate the tile for

    Returns:
        Path to the generated tile
    """
    if not metadata_path.exists():
        raise FileNotFoundError(f'{metadata_path} does not exist')
    if begin_date > end_date:
        raise ValueError('Begin date must be before end date')

    product_name = create_product_name(metadata_path.name, begin_date, end_date)
    product_path = metadata_path.parent / product_name

    frame_map = utils.get_raster_array(metadata_path)

    create_blank_copy_tile(metadata_path, product_path)
    ds = gdal.Open(str(product_path), gdal.GA_Update)
    band = ds.GetRasterBand(1)
    sw_cumul_disp = band.ReadAsArray()

    transfrom = Affine.from_gdal(*gdal.Open(str(metadata_path)).GetGeoTransform())
    frames = frames_from_metadata(metadata_path)
    frame_ids = [x.frame for x in frames]
    needed_granules = find_needed_granules(frame_ids, begin_date, end_date)
    secondary_dates = {}
    for granule in needed_granules:
        granule = open_opera_disp_granule(granule.s3_uri, 'short_wavelength_displacement')
        granule_frame = [x for x in frames if x.frame == granule.attrs['frame']][0]
        granule = update_spatiotemporal_reference(granule, granule_frame)
        granule = granule.rio.reproject('EPSG:3857', transform=transfrom, shape=frame_map.shape)
        frame_locations = frame_map == granule.attrs['frame']
        sw_cumul_disp[frame_locations] = granule.data[frame_locations].astype(float)
        secondary_date = datetime.strftime(granule.attrs['secondary_date'], DATE_FORMAT)
        secondary_dates[f'FRAME_{granule_frame.frame}_SEC_TIME'] = secondary_date

    band.WriteArray(sw_cumul_disp)
    metadata = ds.GetMetadata()
    metadata.update(secondary_dates)
    ds.SetMetadata(metadata)
    ds.FlushCache()
    ds = None
    return product_path


def main():
    """CLI entrpypoint
    Example:
    generate_sw_disp_tile METADATA_ASCENDING_N41W125_N42W124.tif --begin-date 20170901 --end-date 20171231
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('metadata_path', type=str, help='Path to the metadata GeoTiff file')
    parser.add_argument('--begin-date', type=str, help='Start of date range to generate tile for in format: %Y%m%d')
    parser.add_argument('--end-date', type=str, help='End of date range to generate tile for in format: %Y%m%d')

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    create_sw_disp_tile(args.metadata_path, args.begin_date, args.end_date, args.use_profile)


if __name__ == '__main__':
    main()

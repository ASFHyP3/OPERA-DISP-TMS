import argparse
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Tuple

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
class FrameMeta:
    """Dataclass for frame metadata"""

    frame_id: int
    reference_date: datetime
    reference_point_array: tuple  # column, row
    reference_point_geo: tuple  # lon, lat


def frames_from_metadata(metadata_path: Path) -> list[FrameMeta]:
    """Extract frame metadata from a metadata GeoTiff file

    Args:
        metadata_path (Path): Path to the metadata GeoTiff file

    Returns:
        List of frame metadata
    """
    info_dict = gdal.Info(str(metadata_path), format='json')
    frame_metadata = info_dict['metadata']['']
    frame_ids = [int(x) for x in frame_metadata['OPERA_FRAMES'].split(', ')]
    frames = {}
    for frame_id in frame_ids:
        ref_date = datetime.strptime(frame_metadata[f'FRAME_{frame_id}_REF_TIME'], DATE_FORMAT)

        ref_point_array = frame_metadata[f'FRAME_{frame_id}_REF_POINT_ARRAY']
        ref_point_array = tuple([int(x) for x in ref_point_array.split(', ')])

        ref_point_geo = frame_metadata[f'FRAME_{frame_id}_REF_POINT_GEO']
        ref_point_geo = tuple([float(x) for x in ref_point_geo.split(', ')])

        frame = FrameMeta(frame_id, ref_date, ref_point_array, ref_point_geo)
        frames[frame_id] = frame
    return frames


def find_needed_granules(frame_ids: Iterable[int], begin_date: datetime, end_date: datetime) -> list[Granule]:
    """Find the granules needed to generate a short wavelength displacement tile.
    For each `frame_id` the most recent granule whose secondary date is between
    `begin_date` and `end_date` is selected.

    Args:
        frame_ids: The frame ids to generate the tile for
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for

    Returns:
        A list of granules needed to generate the tile
    """
    cali_dataset = find_california_dataset()
    needed_granules = []
    for frame_id in frame_ids:
        granules = [g for g in cali_dataset if g.frame_id == frame_id and begin_date <= g.secondary_date <= end_date]
        if not granules:
            warnings.warn(f'No granules found for frame {frame_id} between {begin_date} and {end_date}.')
        else:
            granule = max(granules, key=lambda x: x.secondary_date)
            needed_granules.append(granule)
    return needed_granules


def update_spatiotemporal_reference(
    in_granule: xr.DataArray, frame: FrameMeta, update_ref_date: bool = True, update_ref_point: bool = True
) -> xr.DataArray:
    """Update the spatiotemporal reference information of a granule to match the frame metadata

    Args:
        in_granule: The granule to update
        frame: The frame metadata to update the granule to
        update_ref_date: Whether to update the reference date
        update_ref_point: Whether to update the reference point

    Returns:
        The updated granule
    """
    if in_granule.attrs['frame_id'] != frame.frame_id:
        raise ValueError('Granule frame does not match frame metadata')

    same_ref_date = utils.round_to_day(in_granule.attrs['reference_date']) == utils.round_to_day(frame.reference_date)
    if not same_ref_date and update_ref_date:
        raise NotImplementedError('Granule reference date does not match frame metadata, this is not yet supported.')

    same_ref_point = np.isclose(in_granule.attrs['reference_point_geo'], frame.reference_point_geo).all()
    if not same_ref_point and update_ref_point:
        # FIXME transform_point may not be working correctly
        ref_x, ref_y = utils.transform_point(
            frame.reference_point_geo[0],
            frame.reference_point_geo[1],
            utils.wkt_from_epsg(4326),
            in_granule['spatial_ref'].attrs['crs_wkt'],
        )
        ref_value = in_granule.sel(x=ref_x, y=ref_y, method='nearest').data.item()
        if np.isnan(ref_value):
            raise ValueError(f'Granule does not contain reference point {ref_x:.2f}, {ref_y:.2f}.')
        in_granule -= ref_value
        in_granule.attrs['reference_point_array'] = frame.reference_point_array
        in_granule.attrs['reference_point_geo'] = frame.reference_point_geo

    return in_granule


def create_product_name(metadata_name: str, begin_date: datetime, end_date: datetime) -> str:
    """Create a product name for a short wavelength cumulative displacement tile
    Takes the form: SW_CUMUL_DISP_YYYYMMDD_YYYYMMDD_ORBIT_BBOX.tif

    Args:
        metadata_name: The name of the metadata file
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for
    """
    parts = metadata_name.split('_')[1:]
    date_fmt = '%Y%m%d'
    begin_date = datetime.strftime(begin_date, date_fmt)
    end_date = datetime.strftime(end_date, date_fmt)
    name = '_'.join(['SW_CUMUL_DISP', begin_date, end_date, *parts])
    return name


def add_granule_data_to_array(
    granule: Granule, frame: FrameMeta, frame_map: np.ndarray, geotransform: Affine, sw_cumul_disp: np.ndarray
) -> Tuple[np.ndarray, datetime]:
    """Add granule data to the short wavelength cumulative displacement array

    Args:
        granule: The granule to add
        frame: The frame metadata
        frame_map: The frame map array
        geotransform: The geotransform of the frame map (Rasterio style)
        sw_cumul_disp: The short wavelength cumulative displacement array

    Returns:
        The updated short wavelength cumulative displacement array and the secondary date of the granule
    """
    granule_dataarray = open_opera_disp_granule(granule.s3_uri, 'short_wavelength_displacement')
    granule_dataarray = update_spatiotemporal_reference(granule_dataarray, frame, update_ref_point=False)
    granule_dataarray = granule_dataarray.rio.reproject('EPSG:3857', transform=geotransform, shape=frame_map.shape)

    frame_locations = frame_map == granule_dataarray.attrs['frame_id']
    sw_cumul_disp[frame_locations] = granule_dataarray.data[frame_locations].astype(float)

    secondary_date = datetime.strftime(granule_dataarray.attrs['secondary_date'], DATE_FORMAT)
    return sw_cumul_disp, secondary_date


def create_sw_disp_tile(metadata_path: Path, begin_date: datetime, end_date: datetime) -> Path:
    """Create a short wavelength cumulative displacement tile.
    Tile is generated using a set of granules whose secondary date are between `begin_date` and
    `end_date`. For each frame, the most recent granule is selected for the tile.

    Args:
        metadata_path: Path to the metadata GeoTiff file
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for

    Returns:
        Path to the generated tile
    """
    if not metadata_path.exists():
        raise FileNotFoundError(f'{metadata_path} does not exist')
    if begin_date > end_date:
        raise ValueError('Begin date must be before end date')

    product_name = create_product_name(metadata_path.name, begin_date, end_date)
    product_path = Path.cwd() / product_name
    print(f'Generating tile {product_name}')

    frames = frames_from_metadata(metadata_path)
    needed_granules = find_needed_granules(list(frames.keys()), begin_date, end_date)

    frame_map, geotransform = utils.get_raster_as_numpy(metadata_path)
    geotransform = Affine.from_gdal(*geotransform)

    sw_cumul_disp = np.full(frame_map.shape, np.nan, dtype=float)
    secondary_dates = {}
    for granule in needed_granules:
        print(f'Granule {granule.scene_name} selected for frame {granule.frame_id}.')
        frame = frames[granule.frame_id]
        sw_cumul_disp, secondary_date = add_granule_data_to_array(
            granule, frame, frame_map, geotransform, sw_cumul_disp
        )
        secondary_dates[f'FRAME_{frame.frame_id}_SEC_TIME'] = secondary_date

    gdal.Translate(str(product_path), str(metadata_path), outputType=gdal.GDT_Float32, format='GTiff')
    ds = gdal.Open(str(product_path), gdal.GA_Update)
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(np.nan)
    band.WriteArray(sw_cumul_disp)
    metadata = ds.GetMetadata()
    metadata.update(secondary_dates)
    ds.SetMetadata(metadata)
    ds.FlushCache()
    ds = None
    print('Done!')
    return product_path


def main():
    """CLI entrpypoint
    Example:
    generate_sw_disp_tile METADATA_ASCENDING_N41W125_N42W124.tif 20170901 20171231
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('metadata_path', type=str, help='Path to the metadata tile')
    parser.add_argument(
        'begin_date', type=str, help='Start of secondary date search range to generate tile for in format: %Y%m%d'
    )
    parser.add_argument(
        'end_date', type=str, help='End of secondary date search range to generate tile for in format: %Y%m%d'
    )

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    create_sw_disp_tile(args.metadata_path, args.begin_date, args.end_date)


if __name__ == '__main__':
    main()

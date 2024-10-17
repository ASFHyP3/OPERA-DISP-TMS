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

from opera_disp_tms.find_california_dataset import Granule, find_california_dataset
from opera_disp_tms.s3_xarray import open_opera_disp_granule
from opera_disp_tms.utils import DATE_FORMAT, create_buffered_bbox, get_raster_as_numpy, round_to_day


gdal.UseExceptions()


@dataclass
class FrameMeta:
    """Dataclass for frame metadata"""

    frame_id: int
    reference_date: datetime
    reference_point_eastingnorthing: tuple  # easting, northing


def extract_frame_metadata(frame_metadata: dict[str, str], frame_id: int) -> FrameMeta:
    """Extract frame metadata from a frame metadata dictionary

    Args:
        frame_metadata: A dictionary of attributes for multiple frames
        frame_id: the ID of the desired frame

    Returns:
        A FrameMeta object for the desired frame
    """
    ref_date = datetime.strptime(frame_metadata[f'FRAME_{frame_id}_REF_TIME'], DATE_FORMAT)

    ref_point_eastingnorthing = frame_metadata[f'FRAME_{frame_id}_REF_POINT_EASTINGNORTHING'].split(', ')
    ref_point_eastingnorthing = tuple(int(x) for x in ref_point_eastingnorthing)

    return FrameMeta(frame_id, ref_date, ref_point_eastingnorthing)


def frames_from_metadata(metadata_path: Path) -> dict[int, FrameMeta]:
    """Extract frame metadata from a metadata GeoTiff file

    Args:
        metadata_path (Path): Path to the metadata GeoTiff file

    Returns:
        Dictionary of frame metadata indexed by frame id
    """
    info_dict = gdal.Info(str(metadata_path), format='json')
    frame_metadata = info_dict['metadata']['']
    frame_ids = [int(x) for x in frame_metadata['OPERA_FRAMES'].split(', ')]
    frames = {frame_id: extract_frame_metadata(frame_metadata, frame_id) for frame_id in frame_ids}
    return frames


def find_needed_granules(
    frame_ids: Iterable[int], begin_date: datetime, end_date: datetime, strategy: str
) -> dict[int, Granule]:
    """Find the granules needed to generate a short wavelength displacement tile.
    For each `frame_id` the most recent granule whose secondary date is between
    `begin_date` and `end_date` is selected.

    Args:
        frame_ids: The frame ids to generate the tile for
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for
        strategy: Selection strategy for granules within search range ("minmax" or "all")
                  - Use "max" to get first granule
                  - Use "minmax" to get first and last granules
                  - Use "all" to get all granules

    Returns:
        A dictionary with form {frame_id: [granules]}
    """
    cali_dataset = find_california_dataset()
    needed_granules = {}
    for frame_id in frame_ids:
        granules = [g for g in cali_dataset if g.frame_id == frame_id and begin_date <= g.secondary_date <= end_date]
        if len(granules) < 2:
            warnings.warn(f'Less than two granules found for frame {frame_id} between {begin_date} and {end_date}.')
        elif strategy == 'max':
            oldest_granule = max(granules, key=lambda x: x.secondary_date)
            needed_granules[frame_id] = [oldest_granule]
        elif strategy == 'minmax':
            youngest_granule = min(granules, key=lambda x: x.secondary_date)
            oldest_granule = max(granules, key=lambda x: x.secondary_date)
            needed_granules[frame_id] = [youngest_granule, oldest_granule]
        elif strategy == 'all':
            needed_granules[frame_id] = granules
        else:
            raise ValueError(f'Invalid strategy: {strategy}. Must be "seacant" or "all".')

    return needed_granules


def create_product_name(
    metadata_name: str, begin_date: datetime, end_date: datetime, prod_type: str = 'SW_CUMUL_DISP'
) -> str:
    """Create a product name for a short wavelength cumulative displacement tile
    Takes the form: SW_CUMUL_DISP_YYYYMMDD_YYYYMMDD_DIRECTION_TILECOORDS.tif

    Args:
        metadata_name: The name of the metadata file
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for
        prod_type: Product type prefix to use
    """
    _, flight_direction, tile_coordinates = metadata_name.split('_')
    date_fmt = '%Y%m%d'
    begin_date = datetime.strftime(begin_date, date_fmt)
    end_date = datetime.strftime(end_date, date_fmt)
    name = '_'.join([prod_type, begin_date, end_date, flight_direction, tile_coordinates])
    return name


def load_sw_disp_granule(granule: Granule, bbox: Iterable[int], frame: FrameMeta) -> xr.DataArray:
    datasets = ['short_wavelength_displacement', 'connected_component_labels']
    granule_xr = open_opera_disp_granule(granule.s3_uri, datasets)

    same_ref_date = round_to_day(granule_xr.attrs['reference_date']) == round_to_day(frame.reference_date)
    if not same_ref_date:
        raise NotImplementedError('Granule reference date does not match metadata tile, this is not supported.')

    granule_xr = granule_xr.rio.clip_box(*bbox, crs='EPSG:3857')
    valid_data_mask = granule_xr['connected_component_labels'] > 0
    sw_cumul_disp_xr = granule_xr['short_wavelength_displacement'].where(valid_data_mask, np.nan)
    sw_cumul_disp_xr.attrs = granule_xr.attrs
    return sw_cumul_disp_xr


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
    bbox = create_buffered_bbox(geotransform.to_gdal(), frame_map.shape, 120)  # EPSG:3857 is in meters
    sw_cumul_disp_xr = load_sw_disp_granule(granule, bbox, frame)

    sw_cumul_disp_xr = sw_cumul_disp_xr.rio.reproject('EPSG:3857', transform=geotransform, shape=frame_map.shape)
    frame_locations = frame_map == sw_cumul_disp_xr.attrs['frame_id']
    sw_cumul_disp[frame_locations] = sw_cumul_disp_xr.data[frame_locations].astype(float)

    secondary_date = datetime.strftime(sw_cumul_disp_xr.attrs['secondary_date'], DATE_FORMAT)
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
    needed_granules = find_needed_granules(list(frames.keys()), begin_date, end_date, strategy='max')

    frame_map, geotransform = get_raster_as_numpy(metadata_path)
    geotransform = Affine.from_gdal(*geotransform)

    sw_cumul_disp = np.full(frame_map.shape, np.nan, dtype=float)
    secondary_dates = {}
    for frame_id, granules in needed_granules.items():
        granule = granules[0]
        print(f'Granule {granule.scene_name} selected for frame {frame_id}.')
        frame = frames[frame_id]
        sw_cumul_disp, secondary_date = add_granule_data_to_array(
            granule, frame, frame_map, geotransform, sw_cumul_disp
        )
        secondary_dates[f'FRAME_{frame_id}_SEC_TIME'] = secondary_date

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
    """CLI entry point
    Example:
    generate_sw_disp_tile METADATA_ASCENDING_N42W124.tif 20170901 20171231
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

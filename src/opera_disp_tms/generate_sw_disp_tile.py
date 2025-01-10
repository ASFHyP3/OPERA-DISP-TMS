import argparse
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import xarray as xr
from osgeo import gdal
from rasterio.transform import Affine

from opera_disp_tms import utils
from opera_disp_tms.s3_xarray import open_opera_disp_granule, s3_xarray_dataset
from opera_disp_tms.search import Granule, find_granules_for_frame


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
    ref_date = datetime.strptime(frame_metadata[f'FRAME_{frame_id}_REF_TIME'], utils.DATE_FORMAT)

    ref_point_eastingnorthing = tuple(
        int(x) for x in frame_metadata[f'FRAME_{frame_id}_REF_POINT_EASTINGNORTHING'].split(', ')
    )

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


def restrict_to_spanning_set(granules: list[Granule]) -> list[Granule]:
    """Restrict a list of granules to the minimum set needed to reconstruct the relative displacement

    Args:
        granules: List of granules to restrict

    Returns:
        List of granules that form the minimum set needed to reconstruct the relative displacement
    """
    assert len(set(g.frame_id for g in granules)) == 1, 'Spanning set granules must be from the same frame.'
    granules = sorted(granules, key=lambda x: x.secondary_date)
    first_reference_date = granules[0].reference_date
    reference_date = granules[-1].reference_date
    spanning_granules = [granules[-1]]
    while not utils.within_one_day(reference_date, first_reference_date):
        possible_connections = [g for g in granules if utils.within_one_day(g.secondary_date, reference_date)]
        if len(possible_connections) == 0:
            raise ValueError('Granules do not form a spanning set.')
        # This could be improved by exploring every branch of the tree, instead of just the longest branch
        next_granule = min(possible_connections, key=lambda x: x.reference_date)
        spanning_granules.append(next_granule)
        reference_date = next_granule.reference_date
    spanning_granules = sorted(spanning_granules, key=lambda x: x.secondary_date)
    return spanning_granules


def find_needed_granules(
    frame_ids: Iterable[int], begin_date: datetime, end_date: datetime, strategy: str, min_granules: int = 2
) -> dict[int, list[Granule]]:
    """Find the granules needed to generate a short wavelength displacement tile.
    For each `frame_id` the most recent granule whose secondary date is between
    `begin_date` and `end_date` is selected.

    Args:
        frame_ids: The frame ids to generate the tile for
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for
        strategy: Selection strategy for granules within search date range ("max", "minmax" or "all")
                  - Use "max" to get last granule
                  - Use "minmax" to get first and last granules
                  - Use "spanning" to get the minimum set of granules needs to reconstruct the relative displacement
                  - Use "all" to get all granules
        min_granules: Minimum number of granules that need to be present in order to return a result

    Returns:
        A dictionary with form {frame_id: [granules]}
    """
    needed_granules = {}
    for frame_id in frame_ids:
        granules_full_stack = find_granules_for_frame(frame_id)
        granules = [g for g in granules_full_stack if begin_date <= g.secondary_date <= end_date]
        if len(granules) < min_granules:
            warnings.warn(
                f'Less than {min_granules} granules found for frame {frame_id} between {begin_date} and {end_date}.'
            )
        elif strategy == 'max':
            oldest_granule = max(granules, key=lambda x: x.secondary_date)
            needed_granules[frame_id] = [oldest_granule]
        elif strategy == 'minmax':
            youngest_granule = min(granules, key=lambda x: x.secondary_date)
            oldest_granule = max(granules, key=lambda x: x.secondary_date)
            needed_granules[frame_id] = [youngest_granule, oldest_granule]
        elif strategy == 'spanning':
            needed_granules[frame_id] = restrict_to_spanning_set(granules)
        elif strategy == 'all':
            needed_granules[frame_id] = granules
        else:
            raise ValueError(f'Invalid strategy: {strategy}. Must be "seacant" or "all".')

    return needed_granules


def load_sw_disp_granule(granule: Granule, bbox: tuple[float, float, float, float]) -> xr.DataArray:
    """Load the short wavelength displacement data for and OPERA DISP granule.
    Clips to frame map and masks out invalid data.

    Args:
        granule: The granule to load
        bbox: The bounding box to clip to

    Returns:
        The short wavelength displacement data as an xarray DataArray
    """
    datasets = ['short_wavelength_displacement', 'recommended_mask']
    with s3_xarray_dataset(granule.s3_uri) as ds:
        granule_xr = open_opera_disp_granule(ds, granule.s3_uri, datasets)
        granule_xr = granule_xr.rio.clip_box(*bbox, crs='EPSG:3857')
        granule_xr = granule_xr.load()
        valid_data_mask = granule_xr['recommended_mask'] == 1
        sw_cumul_disp_xr = granule_xr['short_wavelength_displacement'].where(valid_data_mask, np.nan)
        sw_cumul_disp_xr.attrs = granule_xr.attrs
    sw_cumul_disp_xr.attrs['bbox'] = bbox
    return sw_cumul_disp_xr


def update_reference_date(granule: xr.DataArray, frame: FrameMeta) -> xr.DataArray:
    """Update the reference date of a granule to match the reference date of a frame.

    Note: Assumes that reference date that will be updated is older than the current reference date.

    Args:
        granule: The granule to update
        frame: The frame metadata
    """
    fully_updated = utils.within_one_day(granule.attrs['reference_date'], frame.reference_date)
    while not fully_updated:
        if granule.attrs['reference_date'] < frame.reference_date:
            raise ValueError('Granule reference date is older than frame reference date, cannot be updated.')
        prev_ref_date = granule.attrs['reference_date']
        prev_ref_date_min = prev_ref_date - timedelta(days=1)
        prev_ref_date_max = prev_ref_date + timedelta(days=1)
        # We can assume that there is only one granule for a frame that has
        # a secondary date equal to another granule's reference date
        granule_dict = find_needed_granules(
            [frame.frame_id], prev_ref_date_min, prev_ref_date_max, strategy='max', min_granules=1
        )
        older_granule_meta = granule_dict[frame.frame_id][0]
        older_granule = load_sw_disp_granule(older_granule_meta, granule.attrs['bbox'])
        granule += older_granule
        granule.attrs['reference_date'] = older_granule.attrs['reference_date']
        fully_updated = utils.within_one_day(granule.attrs['reference_date'], frame.reference_date)

    return granule


def add_granule_data_to_array(
    granule: Granule, frame: FrameMeta, frame_map: np.ndarray, geotransform: Affine, sw_cumul_disp: np.ndarray
) -> tuple[np.ndarray, str]:
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
    bbox = utils.create_buffered_bbox(geotransform.to_gdal(), frame_map.shape, 120)  # EPSG:3857 is in meters
    sw_cumul_disp_xr = load_sw_disp_granule(granule, bbox)
    update_reference_date(sw_cumul_disp_xr, frame)

    sw_cumul_disp_xr = sw_cumul_disp_xr.rio.reproject('EPSG:3857', transform=geotransform, shape=frame_map.shape)
    frame_locations = frame_map == sw_cumul_disp_xr.attrs['frame_id']
    sw_cumul_disp[frame_locations] = sw_cumul_disp_xr.data[frame_locations].astype(float)

    secondary_date = datetime.strftime(sw_cumul_disp_xr.attrs['secondary_date'], utils.DATE_FORMAT)
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

    product_name = utils.create_tile_name(metadata_path.name, begin_date, end_date)
    product_path = Path.cwd() / product_name
    print(f'Generating tile {product_name}')

    frames = frames_from_metadata(metadata_path)
    needed_granules = find_needed_granules(list(frames.keys()), begin_date, end_date, strategy='max')

    frame_map, geotransform = utils.get_raster_as_numpy(metadata_path)
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

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from osgeo import gdal
from rasterio.transform import Affine

from opera_disp_tms import utils
from opera_disp_tms.prep_stack import load_sw_disp_stack


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


def add_granule_data_to_array(
    frame_id: FrameMeta,
    frame_map: np.ndarray,
    geotransform: Affine,
    begin_date: datetime,
    end_date: datetime,
    sw_cumul_disp: np.ndarray,
) -> tuple[np.ndarray, str]:
    """Add granule data to the short wavelength cumulative displacement array

    Args:
        frame_id: The frame id
        frame_map: The frame map array
        geotransform: The geotransform of the frame map (Rasterio style)
        begin_date: The start of the date range
        end_date: The end of the date range
        sw_cumul_disp: The short wavelength cumulative displacement array

    Returns:
        The updated short wavelength cumulative displacement array and the secondary date of the granule
    """
    bbox = utils.create_buffered_bbox(geotransform.to_gdal(), frame_map.shape, 120)  # EPSG:3857 is in meters
    sw_cumul_disp_xr = load_sw_disp_stack(frame_id, bbox, begin_date, end_date, 'spanning')[-1]
    sw_cumul_disp_xr = sw_cumul_disp_xr.rio.reproject('EPSG:3857', transform=geotransform, shape=frame_map.shape)
    frame_locations = frame_map == sw_cumul_disp_xr.attrs['frame_id']
    sw_cumul_disp[frame_locations] = sw_cumul_disp_xr.data[frame_locations].astype(float)
    secondary_date = datetime.strftime(sw_cumul_disp_xr.attrs['secondary_date'], utils.DATE_FORMAT)
    return sw_cumul_disp, secondary_date


def create_sw_disp_tile(frame_id: int, begin_date: datetime, end_date: datetime) -> Path:
    """Create a short wavelength cumulative displacement tile.
    Tile is generated using a set of granules whose secondary date are between `begin_date` and
    `end_date`. For each frame, the most recent granule is selected for the tile.

    Args:
        metadata_path: Path to the metadata GeoTiff file
        begin_date: The start of the date range
        end_date: The end of the date range

    Returns:
        Path to the generated tile
    """
    product_name = utils.create_tile_name(frame_id, begin_date, end_date)
    product_path = Path.cwd() / product_name

    data = load_sw_disp_stack(frame_id, begin_date, end_date, 'spanning')[-1]
    data.rio.to_raster(product_path.name, nodata=np.nan)
    return product_path


def main():
    """CLI entry point
    Example:
    generate_sw_disp_tile METADATA_ASCENDING_N42W124.tif 20170901 20171231
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('metadata_path', type=str, help='Path to the metadata tile')
    parser.add_argument(
        'begin_date', type=str, help='Start of date search range to generate tile for in format: %Y%m%d'
    )
    parser.add_argument('end_date', type=str, help='End of date search range to generate tile for in format: %Y%m%d')

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    create_sw_disp_tile(args.metadata_path, args.begin_date, args.end_date)


if __name__ == '__main__':
    main()

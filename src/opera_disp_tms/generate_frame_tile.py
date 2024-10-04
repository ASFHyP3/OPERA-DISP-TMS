import argparse
import warnings
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pyproj
from osgeo import gdal, ogr, osr
from shapely.ops import transform

from opera_disp_tms.find_california_dataset import Granule, find_california_dataset
from opera_disp_tms.frames import Frame, intersect
from opera_disp_tms.s3_xarray import get_opera_disp_granule_metadata
from opera_disp_tms.utils import check_bbox_all_int


gdal.UseExceptions()


def create_product_name(parts: Iterable[str], orbit_pass: str, bbox: Iterable[int]) -> str:
    """Create a product name for a frame metadata tile
    Should be in the format: metadata_ascending_N02E001 where N02E001 is the upper left corner

    Args:
        parts: The parts of the product name
        orbit_pass: The orbit pass of the frames
        bbox: The bounding box of the frames

    Returns:
        The product name
    """
    check_bbox_all_int(bbox)

    def lat_string(lat):
        return ('N' if lat >= 0 else 'S') + f'{abs(lat):02}'

    def lon_string(lon):
        return ('E' if lon >= 0 else 'W') + f'{abs(lon):03}'

    bbox_str = f'{lon_string(bbox[0])}{lat_string(bbox[3])}'
    return '_'.join([*parts, orbit_pass, bbox_str]).upper()


def update_frame_geometry(frame: Frame, buffer_size: int = -3500) -> Frame:
    """Apply a buffer to the geometry of a frame to better align it with OPERA DISP granules

    Args:
        frame: The frame to update
        buffer_size: The buffer size to apply to the geometry

    Returns:
        The updated frame
    """
    crs_latlon = pyproj.CRS('EPSG:4326')
    crs_utm = pyproj.CRS(f'EPSG:{frame.epsg}')

    latlon2utm = pyproj.Transformer.from_crs(crs_latlon, crs_utm, always_xy=True).transform
    geom_utm = transform(latlon2utm, frame.geom)

    geom_shrunk = geom_utm.buffer(buffer_size, join_style='mitre')

    utm2latlon = pyproj.Transformer.from_crs(crs_utm, crs_latlon, always_xy=True).transform
    geom_latlon = transform(utm2latlon, geom_shrunk)
    frame.geom = geom_latlon
    return frame


def reorder_frames(frame_list: Iterable[Frame], order_by: str = 'west_most') -> List[Frame]:
    """Reorder a set of frames so that they overlap correctly when rasterized.
    Frames within a relative orbit are stacked so that higher frame numbers are on top (so they are rasterized first).
    Relative orbits sets are orderd by either frame number, or from west to east.

    Args:
        frame_list: The list of frames to reorder
        order_by: Strategy to use when ordering relative orbit sets (`frame_number`, or `west_most`)

    Returns:
        The reordered list of frames
    """
    if len({x.orbit_pass for x in frame_list}) > 1:
        raise ValueError('Cannot reorder frames with different orbit passes')

    orbits = list({frame.relative_orbit_number for frame in frame_list})
    orbit_groups = {}
    for orbit in orbits:
        frames = [frame for frame in frame_list if frame.relative_orbit_number == orbit]
        frames = sorted(frames, key=lambda x: x.frame_id, reverse=True)

        if order_by == 'frame_number':
            metric = max([x.frame_id for x in frames])
        elif order_by == 'west_most':
            metric = max([x.geom.bounds[0] for x in frames])
        else:
            raise ValueError('Invalid order_by parameter. Please use "frame_number" or "west_most".')

        orbit_groups[orbit] = (metric, frames)

    sorted_orbits = sorted(orbit_groups, key=lambda x: orbit_groups[x][0], reverse=True)
    sorted_frames = [orbit_groups[orbit][1] for orbit in sorted_orbits]
    sorted_frames = [frame for sublist in sorted_frames for frame in sublist]
    return sorted_frames


def create_empty_frame_tile(bbox: Iterable[int], out_path: Path, resolution: int = 30) -> Path:
    """Create an empty frame metadata tile in EPSG:3857 with a 30 m resolution

    Args:
        bbox: The bounding box to create the frame for in the
              (minx, miny, maxx, maxy) in EPSG:4326, integers only.
        out_path: The path to save the empty frame metadata tile to

    Returns:
        The path to the empty frame metadata tile
    """
    check_bbox_all_int(bbox)
    min_lon, min_lat, max_lon, max_lat = bbox

    wgs84 = osr.SpatialReference()
    wgs84.ImportFromEPSG(4326)

    mercator = osr.SpatialReference()
    mercator.ImportFromEPSG(3857)

    transform = osr.CoordinateTransformation(wgs84, mercator)

    min_x, min_y, _ = transform.TransformPoint(min_lat, min_lon)
    max_x, max_y, _ = transform.TransformPoint(max_lat, max_lon)

    x_size = int((max_x - min_x) / resolution) + 1
    y_size = int((max_y - min_y) / resolution) + 1

    driver = gdal.GetDriverByName('GTiff')
    opts = ['TILED=YES', 'COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS']
    ds = driver.Create(out_path, x_size, y_size, 1, gdal.GDT_UInt16, options=opts)

    ds.SetGeoTransform((min_x, resolution, 0, max_y, 0, -resolution))
    ds.SetProjection(mercator.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.WriteArray(np.zeros((y_size, x_size), dtype=np.uint16))
    band.SetNoDataValue(0)

    band.FlushCache()
    ds = None


def burn_frame(frame: Frame, tile_path: Path):
    """Burn the frame id into the frame metadata tile within the frame geometry

    Args:
        frame: The frame to burn into the tile
        tile_path: The path to the frame metadata tile
    """
    tile_ds = gdal.Open(tile_path, gdal.GA_Update)
    geotransform = tile_ds.GetGeoTransform()
    projection = tile_ds.GetProjection()
    width = tile_ds.RasterXSize
    height = tile_ds.RasterYSize

    # Create a raster to hold the rasterized polygon
    tmp_tiff = tile_path.with_suffix(f'.{frame.frame_id}.tif')
    driver = gdal.GetDriverByName('GTiff')
    tmp_ds = driver.Create(str(tmp_tiff), width, height, 1, gdal.GDT_UInt16)
    tmp_ds.SetGeoTransform(geotransform)
    tmp_ds.SetProjection(projection)

    # Create an empty array to store the rasterized data (initially all zeros)
    tmp_band = tmp_ds.GetRasterBand(1)
    tmp_band.SetNoDataValue(0)
    tmp_band.Fill(0)

    # Convert the Shapely polygon to an OGR geometry
    project = pyproj.Transformer.from_crs(pyproj.CRS('EPSG:4326'), pyproj.CRS('EPSG:3857'), always_xy=True).transform
    geom_epsg3857 = transform(project, frame.geom)
    ogr_polygon = ogr.CreateGeometryFromWkt(geom_epsg3857.wkt)

    # Create a layer and feature for the polygon
    tmp_srs = osr.SpatialReference()
    tmp_srs.ImportFromWkt(projection)
    ogr_ds = ogr.GetDriverByName('Memory').CreateDataSource('memDataSource')
    layer = ogr_ds.CreateLayer('memLayer', srs=tmp_srs, geom_type=ogr.wkbPolygon)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(ogr_polygon)
    layer.CreateFeature(feature)

    # Rasterize the polygon onto the output raster
    gdal.RasterizeLayer(tmp_ds, [1], layer, burn_values=[frame.frame_id])

    # Close and flush the dataset to disk
    tmp_band.FlushCache()
    tmp_ds = None

    # Reopen the dataset and copy the data to the tile
    frame_ds = gdal.Open(str(tmp_tiff))
    frame_array = frame_ds.GetRasterBand(1).ReadAsArray()

    tile_band = tile_ds.GetRasterBand(1)
    tile_array = tile_band.ReadAsArray()
    tile_array[frame_array != 0] = frame_array[frame_array != 0]
    tile_band.WriteArray(tile_array)

    # Clean up
    frame_ds.FlushCache()
    frame_ds = None
    tile_band.FlushCache()
    tile_ds = None
    tmp_tiff.unlink()


def create_granule_metadata_dict(granule: Granule) -> Dict:
    """Create a dictionary of metadata for a granule to add to the frame metadata tile

    Args:
        granule: The granule to create the metadata dictionary for

    Returns:
        The granule metadata dictionary
    """
    granule_info = get_opera_disp_granule_metadata(granule.s3_uri)
    ref_point_array, ref_point_geo, epsg, reference_date, frame, _ = granule_info
    frame_metadata = {}
    frame_metadata[f'FRAME_{frame}_REF_POINT_ARRAY'] = ', '.join([str(x) for x in ref_point_array])
    frame_metadata[f'FRAME_{frame}_REF_POINT_GEO'] = ', '.join([str(x) for x in ref_point_geo])
    frame_metadata[f'FRAME_{frame}_EPSG'] = str(epsg)
    frame_metadata[f'FRAME_{frame}_REF_TIME'] = granule.reference_date.strftime('%Y%m%dT%H%M%SZ')
    frame_metadata[f'FRAME_{frame}_REF_DATE'] = granule.reference_date.strftime('%Y-%m-%d')
    return frame_metadata


def add_frames_to_tile(frames: Iterable[Frame], tile_path: Path) -> None:
    """Add frame information to a frame metadata tile

    Args:
        frames: The frames to add to the tile
        tile_path: The path to the frame metadata tile
    """
    cal_data = find_california_dataset()
    frame_metadata = {}
    for frame in frames:
        relevant_granules = [x for x in cal_data if x.frame == frame.frame_id]
        if len(relevant_granules) == 0:
            warnings.warn(f'No granules found for frame {frame}, this frame will not be added to the tile.')
        else:
            first_granule = min(relevant_granules, key=lambda x: x.reference_date)
            frame_metadata[frame.frame_id] = create_granule_metadata_dict(first_granule)
            burn_frame(frame, tile_path)

    tile_ds = gdal.Open(str(tile_path), gdal.GA_Update)
    # Not all frames will be in the final array, so we need to find the included frames
    band = tile_ds.GetRasterBand(1)
    array = band.ReadAsArray()
    included_frames = np.unique(array)

    metadata_dict = {'OPERA_FRAMES': ', '.join([str(frame) for frame in included_frames])}
    [metadata_dict.update(frame_metadata[x]) for x in included_frames]
    tile_ds.SetMetadata(metadata_dict)
    tile_ds.FlushCache()
    tile_ds = None


def create_tile_for_bbox(bbox: Iterable[int], direction: str) -> Path:
    """Create the frame metadata tile for a specific bounding box

    Args:
        bbox: The bounding box to create the frame for in the (minx, miny, maxx, maxy) in EPSG:4326, integers only.
        direction: The direction of the orbit pass ('ascending' or 'descending')

    Returns:
        The path to the frame metadata tile
    """
    check_bbox_all_int(bbox)
    direction = direction.upper()
    if direction not in ['ASCENDING', 'DESCENDING']:
        raise ValueError('Direction must be either "ASCENDING" or "DESCENDING"')
    out_path = Path(create_product_name(['metadata'], direction, bbox) + '.tif')
    relevant_frames = intersect(bbox=bbox, orbit_pass=direction, is_north_america=True, is_land=True)
    updated_frames = [update_frame_geometry(x) for x in relevant_frames]
    ordered_frames = reorder_frames(updated_frames)
    create_empty_frame_tile(bbox, out_path)
    add_frames_to_tile(ordered_frames, out_path)
    return out_path


def main():
    """CLI entrypoint
    Example: generate_frame_tile -125 41 -124 42 --ascending
    """
    parser = argparse.ArgumentParser(description='Create a frame metadata tile for a given bounding box')
    parser.add_argument('bbox', type=int, nargs=4, help='Bounding box in the form of min_lon min_lat max_lon max_lat')
    parser.add_argument(
        '--direction', type=str, choices=['ascending', 'descending'], help='Direction of the orbit pass'
    )
    args = parser.parse_args()
    create_tile_for_bbox(args.bbox, direction=args.direction)


if __name__ == '__main__':
    main()

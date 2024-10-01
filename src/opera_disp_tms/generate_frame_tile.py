import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import h5py
import numpy as np
import pyproj
import s3fs
from osgeo import gdal, ogr, osr
from shapely.ops import transform

from opera_disp_tms.find_california_dataset import find_california_dataset
from opera_disp_tms.frames import Frame, intersect
from opera_disp_tms.tmp_s3_access import get_credentials


gdal.UseExceptions()


def check_bbox_all_int(bbox: Iterable[int]):
    if not all(isinstance(i, int) for i in bbox):
        raise ValueError('Bounding box must be integers')


def create_product_name(parts: Iterable[str], orbit_pass: str, bbox: Iterable[int]) -> str:
    """Create a product name for a frame metadata tile
    Should be in the format: metadata_ascendign_N02E001_N04E003

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

    bbox_str = f'{lat_string(bbox[1])}{lon_string(bbox[0])}_{lat_string(bbox[3])}{lon_string(bbox[2])}'
    return '_'.join([*parts, orbit_pass, bbox_str]).upper()


def reorder_frames(frame_list: Iterable[Frame], order_by: str = 'west_most') -> List[Frame]:
    """Reorder the frames based on the relative orbit number

    Args:
        frame_list: The list of frames to reorder

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
    raster = driver.Create(out_path, x_size, y_size, 1, gdal.GDT_UInt16, options=opts)

    raster.SetGeoTransform((min_x, resolution, 0, max_y, 0, -resolution))
    raster.SetProjection(mercator.ExportToWkt())
    band = raster.GetRasterBand(1)
    band.WriteArray(np.zeros((y_size, x_size), dtype=np.uint16))

    band.FlushCache()
    raster = None


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


def get_granule_reference_info_s3(s3_granule_path: str) -> Tuple:
    """Get the reference information for an OPERA DISP granule stored in S3

    Args:
        s3_granule_path: The S3 URI to the granule

    Returns:
        A tuple containing the reference point in array coordinates, geographic coordinates, and EPSG code
    """
    io_params = {
        's3fs_params': {
            'default_cache_type': 'blockcache',
            'default_block_size': 8 * 1024 * 1024,
        },
        'h5py_params': {
            'driver_kwds': {
                'page_buf_size': 32 * 1024 * 1024,
                'rdcc_nbytes': 8 * 1024 * 1024,
            }
        },
    }
    creds = get_credentials()
    fs = s3fs.S3FileSystem(
        key=creds['accessKeyId'],
        secret=creds['secretAccessKey'],
        token=creds['sessionToken'],
        **io_params['s3fs_params'],
    )
    with fs.open(s3_granule_path, 'rb') as f:
        with h5py.File(f, 'r', **io_params['h5py_params']['driver_kwds']) as hdf:
            ref_point_array, ref_point_geo, epsg = read_reference_info(hdf)
    return ref_point_array, ref_point_geo, epsg


def read_reference_info(h5_fobj: h5py.File) -> Tuple:
    """Find the reference information for an OPERA DISP granule

    Args:
        h5_fobj: An open HDF5 file object for an OPERA DISP granule

    Returns:
        A tuple containing the reference point in array coordinates, geographic coordinates, and EPSG code
    """
    ref_point = h5_fobj['corrections']['reference_point'].attrs
    ref_col = int(ref_point['cols'][0])
    ref_row = int(ref_point['rows'][0])
    ref_lat = float(ref_point['latitudes'][0])
    ref_lon = float(ref_point['longitudes'][0])

    srs = osr.SpatialReference()
    srs.ImportFromWkt(h5_fobj['spatial_ref'].attrs['crs_wkt'])
    epsg = int(srs.GetAuthorityCode(None))

    ref_point_geo = (ref_lon, ref_lat)
    ref_point_array = (ref_col, ref_row)
    return ref_point_array, ref_point_geo, epsg


def add_metadata_to_tile(tile_path: Path, ascending=True) -> None:
    """Add metadata to the frame metadata tile

    Args:
        tile_path: The path to the frame metadata tile
    """
    tile_ds = gdal.Open(str(tile_path), gdal.GA_Update)
    band = tile_ds.GetRasterBand(1)
    array = band.ReadAsArray()
    frames = np.unique(array)

    cal_data = find_california_dataset()
    frame_metadata = {}
    for frame in frames:
        first_granule = min([x for x in cal_data if x.frame == frame], key=lambda x: x.reference_date)

        ref_point_array, ref_point_geo, epsg = get_granule_reference_info_s3(first_granule.s3_uri)
        frame_metadata[f'FRAME_{frame}_REF_POINT_ARRAY'] = ', '.join([str(x) for x in ref_point_array])
        frame_metadata[f'FRAME_{frame}_REF_POINT_GEO'] = ', '.join([str(x) for x in ref_point_geo])
        frame_metadata[f'FRAME_{frame}_EPSG'] = str(epsg)

        frame_metadata[f'FRAME_{frame}_REF_TIME'] = first_granule.reference_date.strftime('%Y%m%dT%H%M%SZ')

    tile_ds.SetMetadata({'OPERA_FRAMES': ', '.join([str(frame) for frame in frames]), **frame_metadata})

    tile_ds.FlushCache()
    tile_ds = None


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

    return frame
    frame.geom = geom_latlon


def create_tile_for_bbox(bbox, ascending=True) -> Path:
    """Create the frame metadata tile for a specific bounding box

    Args:
        bbox: The bounding box to create the frame for in the
              (minx, miny, maxx, maxy) in EPSG:4326, integers only.

    Returns:
        The path to the frame metadata tile
    """
    check_bbox_all_int(bbox)
    orbit_pass = 'ASCENDING' if ascending else 'DESCENDING'
    out_path = Path(create_product_name(['metadata'], orbit_pass, bbox) + '.tif')
    relevant_frames = intersect(bbox=bbox, orbit_pass=orbit_pass, is_north_america=True, is_land=True)
    updated_frames = [update_frame_geometry(x) for x in relevant_frames]
    ordered_frames = reorder_frames(updated_frames)
    create_empty_frame_tile(bbox, out_path)
    for frame in ordered_frames:
        burn_frame(frame, out_path)
    add_metadata_to_tile(out_path)
    return out_path


def main():
    """CLI entrpypoint
    Example: generate_frame_tile -125 41 -124 42 --ascending
    """
    parser = argparse.ArgumentParser(description='Create a frame metadata tile for a given bounding box')
    parser.add_argument('bbox', type=int, nargs=4, help='Bounding box in the form of min_lon min_lat max_lon max_lat')
    parser.add_argument('--ascending', action='store_true', help='Use ascending orbit pass')
    args = parser.parse_args()
    create_tile_for_bbox(args.bbox, ascending=args.ascending)


if __name__ == '__main__':
    main()

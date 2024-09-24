from pathlib import Path
from typing import Iterable, List

import pyproj
from osgeo import gdal, ogr, osr
from shapely.ops import transform

from opera_disp_tms.frames import Frame, intersect


gdal.UseExceptions()


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
    # tmp_tiff.unlink()


def create_empty_frame_tile(bbox: Iterable[int], out_path: Path) -> Path:
    """Create an empty frame metadata tile in EPSG:3857 with a 30 m resolution

    Args:
        bbox: The bounding box to create the frame for in the
              (minx, miny, maxx, maxy) in EPSG:4326, integers only.
        out_path: The path to save the empty frame metadata tile to

    Returns:
        The path to the empty frame metadata tile
    """
    if not all(isinstance(i, int) for i in bbox):
        raise ValueError('Bounding box must be integers')

    # Create an empty frame tile in EPSG:4326 that spans the given bounding box
    tmp_path = out_path.with_suffix('.vrt')
    driver = gdal.GetDriverByName('VRT')
    ds = driver.Create(str(tmp_path), 1, 1, 1, gdal.GDT_UInt16)
    ds.SetGeoTransform([bbox[0], 1, 0, bbox[3], 0, -1])
    ds.SetProjection('EPSG:4326')
    ds = None

    # Reproject to EPSG:3857 with a 30 m resolution
    gdal.Warp(str(out_path), str(tmp_path), dstSRS='EPSG:3857', xRes=30, yRes=30)
    tmp_path.unlink()
    return out_path


def reorder_frames(frame_list: Iterable[Frame]) -> List[Frame]:
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
        westmost = max([x.geom.bounds[0] for x in frames])
        orbit_groups[orbit] = (westmost, frames)

    # TODO: check anti-meridian crossing
    sorted_orbits = sorted(orbit_groups, key=lambda x: orbit_groups[x][0], reverse=True)
    sorted_frames = [orbit_groups[orbit][1] for orbit in sorted_orbits]
    sorted_frames = [frame for sublist in sorted_frames for frame in sublist]
    return sorted_frames


def create_frame_for_bbox(bbox, ascending=True) -> Path:
    """Create the frame metadata tile for a specific bounding box

    Args:
        bbox: The bounding box to create the frame for in the
              (minx, miny, maxx, maxy) in EPSG:4326, integers only.

    Returns:
        The path to the frame metadata tile
    """
    out_path = Path('frame.tif')
    if not all(isinstance(i, int) for i in bbox):
        raise ValueError('Bounding box must be integers')

    orbit_pass = 'ASCENDING' if ascending else 'DESCENDING'
    relevant_frames = intersect(bbox=bbox, orbit_pass=orbit_pass, is_north_america=True, is_land=True)
    ordered_frames = reorder_frames(relevant_frames)
    create_empty_frame_tile(bbox, out_path)
    for frame in ordered_frames:
        burn_frame(frame, out_path)
    return out_path


if __name__ == '__main__':
    # non_na_ocean = (-131, 26, -130, 27)
    bbox = (-122, 37, -121, 38)
    create_frame_for_bbox(bbox)

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple, Union

import requests
from hyp3lib.aws import upload_file_to_s3
from osgeo import gdal, osr
from pyproj import Transformer


gdal.UseExceptions()

DATE_FORMAT = '%Y%m%dT%H%M%SZ'


def get_raster_as_numpy(raster_path: Path, band: int = 1) -> Tuple:
    """Get data, geotransform, and shape of a raseter

    Args:
        raster_path: Path to the raster file

    Returns:
        raster's numpy array and geostransform
    """
    raster = gdal.Open(str(raster_path))
    band = raster.GetRasterBand(band)
    data = band.ReadAsArray()
    geostransform = raster.GetGeoTransform()
    return data, geostransform


def download_file(
    url: str,
    download_path: Union[Path, str] = '.',
    chunk_size=10 * (2**20),
) -> Path:
    """Download a file without authentication.

    Args:
        url: URL of the file to download
        download_path: Path to save the downloaded file to
        chunk_size: Size to chunk the download into

    Returns:
        download_path: The path to the downloaded file
    """
    session = requests.Session()

    with session.get(url, stream=True) as s:
        s.raise_for_status()
        with open(download_path, 'wb') as f:
            for chunk in s.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    session.close()


def within_one_day(date1: datetime, date2: datetime) -> bool:
    """Check if two dates are within one day of each other"""
    return abs(date1 - date2) <= timedelta(days=1)


def wkt_from_epsg(epsg_code: int) -> str:
    """Get the WKT from an EPSG code

    Args:
        epsg_code: EPSG code to get the WKT for

    Returns:
        WKT for the EPSG code
    """
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    wkt = srs.ExportToWkt()
    return wkt


def transform_point(x: float, y: float, source_wkt: str, target_wkt: str) -> Tuple[float]:
    """Transform a point from one coordinate system to another

    Args:
        x: x coordinate in the source coordinate system
        y: y coordinate in the source coordinate system
        source_wkt: WKT of the source coordinate system
        target_wkt: WKT of the target coordinate system

    Returns:
        x_transformed: x coordinate in the target coordinate system
        y_transformed: y coordinate in the target coordinate system
    """
    transformer = Transformer.from_crs(source_wkt, target_wkt, always_xy=True)
    x_transformed, y_transformed = transformer.transform(x, y)
    return x_transformed, y_transformed


def create_buffered_bbox(geotransform: Iterable[int], shape: Iterable[int], buffer_size: float) -> Tuple[float]:
    """Create a buffered bounding box from a geotransform and shape

    Args:
        geotransform: Geotransform of the raster in GDAL style
        shape: Shape of the raster (n_rows, n_cols)
        buffer_size: Size of the buffer to add to the bounding box in the same units as the geotransform

    Returns:
        Bounding box in the form (minx, miny, maxx, maxy)
    """
    minx, xres, _, maxy, _, yres = geotransform
    miny = maxy + (shape[0] * yres)
    maxx = minx + (shape[1] * xres)
    minx -= buffer_size
    maxx += buffer_size
    miny -= buffer_size
    maxy += buffer_size
    return minx, miny, maxx, maxy


def validate_bbox(bbox: Iterable[int]) -> None:
    """Check that bounding box:
    - Has four elements
    - All elements are integers
    - Minx is less than maxx
    - Miny is less than maxy

    Args:
        bbox: Bounding box to check
    """
    if len(bbox) != 4:
        raise ValueError('Bounding box must have 4 elements')

    if not all(isinstance(i, int) for i in bbox):
        raise ValueError('Bounding box must be integers')

    if bbox[0] > bbox[2]:
        raise ValueError('Bounding box minx is greater than maxx')

    if bbox[1] > bbox[3]:
        raise ValueError('Bounding box miny is greater than maxy')


def create_tile_name(
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


def upload_dir_to_s3(path_to_dir: Path, bucket: str, prefix: str = ''):
    """Upload a local directory, subdirectory, and all contents to an S3 bucket

    Args:
        path_to_dir: The local path to directory
        bucket: S3 bucket to which the directory should be uploaded
        prefix: prefix in S3 bucket to upload the directory to. Defaults to ''
    """
    for branch in os.walk(path_to_dir, topdown=True):
        branch_path = branch[0]
        for filename in branch[2]:
            path_to_file = Path(branch_path) / filename
            file_prefix = str(prefix / path_to_file.relative_to(path_to_dir).parent)
            upload_file_to_s3(path_to_file, bucket, file_prefix)

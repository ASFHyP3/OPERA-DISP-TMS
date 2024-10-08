from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple, Union

import requests
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


def round_to_day(dt: datetime) -> datetime:
    """Round a datetime to the nearest day

    Args:
        dt: Datetime to round

    Returns:
        The rounded datetime
    """
    return (dt + timedelta(hours=12)).replace(hour=0, minute=0, second=0, microsecond=0)


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

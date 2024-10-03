from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple, Union

import numpy as np
import requests
from osgeo import gdal, osr


gdal.UseExceptions()


DATE_FORMAT = '%Y%m%dT%H%M%SZ'


def get_raster_array(raster_path: Path, band: int = 1) -> np.ndarray:
    """Read a raster band as a numpy array

    Args:
        raster_path: Path to the raster file
        band: Band to read

    Returns:
        Numpy array of the raster band
    """
    ds = gdal.Open(str(raster_path))
    band = ds.GetRasterBand(band)
    frame_map = band.ReadAsArray()
    ds = None
    return frame_map


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
    source_srs = osr.SpatialReference()
    source_srs.ImportFromWkt(source_wkt)

    target_srs = osr.SpatialReference()
    target_srs.ImportFromWkt(target_wkt)

    transform = osr.CoordinateTransformation(source_srs, target_srs)
    # For some reason, the order of x and y is reversed in the function call
    y_transformed, x_transformed, z_transformed = transform.TransformPoint(y, x)
    return x_transformed, y_transformed


def check_bbox_all_int(bbox: Iterable[int]) -> None:
    """Check that all elements of a bounding box are integers

    Args:
        bbox: Bounding box to check
    """
    if not all(isinstance(i, int) for i in bbox):
        raise ValueError('Bounding box must be integers')

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Union

import requests
import rioxarray  # noqa
import s3fs
import xarray as xr
from osgeo import osr

from opera_disp_tms.tmp_s3_access import get_credentials


DATE_FORMAT = '%Y%m%dT%H%M%SZ'
IO_PARAMS = {
    'fsspec_params': {
        # "skip_instance_cache": True
        'cache_type': 'blockcache',  # or "first" with enough space
        'block_size': 8 * 1024 * 1024,  # could be bigger
    },
    'h5py_params': {
        'driver_kwds': {  # only recent versions of xarray and h5netcdf allow this correctly
            'page_buf_size': 32 * 1024 * 1024,  # this one only works in repacked files
            'rdcc_nbytes': 8 * 1024 * 1024,  # this one is to read the chunks
        }
    },
}


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


def round_to_nearest_day(dt: datetime) -> datetime:
    return (dt + timedelta(hours=12)).replace(hour=0, minute=0, second=0, microsecond=0)


def wkt_from_epsg(epsg_code):
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    wkt = srs.ExportToWkt()
    return wkt


def transform_point(x, y, source_wkt, target_wkt):
    source_srs = osr.SpatialReference()
    source_srs.ImportFromWkt(source_wkt)

    target_srs = osr.SpatialReference()
    target_srs.ImportFromWkt(target_wkt)

    transform = osr.CoordinateTransformation(source_srs, target_srs)
    x_transformed, y_transformed, _ = transform.TransformPoint(y, x)
    return x_transformed, y_transformed


def check_bbox_all_int(bbox: Iterable[int]):
    if not all(isinstance(i, int) for i in bbox):
        raise ValueError('Bounding box must be integers')


def open_opera_disp_granule(s3_uri: str, dataset=str):
    creds = get_credentials()
    s3_fs = s3fs.S3FileSystem(key=creds['accessKeyId'], secret=creds['secretAccessKey'], token=creds['sessionToken'])
    ds = xr.open_dataset(
        s3_fs.open(s3_uri, **IO_PARAMS['fsspec_params']),
        engine='h5netcdf',
        **IO_PARAMS['h5py_params'],
    )
    data = ds[dataset]
    ds_metadata = xr.open_dataset(
        s3_fs.open(s3_uri, **IO_PARAMS['fsspec_params']),
        group='/corrections',
        engine='h5netcdf',
        **IO_PARAMS['h5py_params'],
    )
    row = int(ds_metadata['reference_point'].attrs['rows'])
    col = int(ds_metadata['reference_point'].attrs['cols'])
    data.attrs['reference_point_array'] = (row, col)

    longitude = float(ds_metadata['reference_point'].attrs['longitudes'])
    latitude = float(ds_metadata['reference_point'].attrs['latitudes'])
    data.attrs['reference_point_geo'] = (longitude, latitude)

    reference_date = datetime.strptime(s3_uri.split('/')[-1].split('_')[6], DATE_FORMAT)
    data.attrs['reference_date'] = reference_date

    secondary_date = datetime.strptime(s3_uri.split('/')[-1].split('_')[7], DATE_FORMAT)
    data.attrs['secondary_date'] = secondary_date

    frame = int(s3_uri.split('/')[-1].split('_')[4][1:])
    data.attrs['frame'] = frame

    data.rio.write_crs(ds['spatial_ref'].attrs['crs_wkt'], inplace=True)
    return data

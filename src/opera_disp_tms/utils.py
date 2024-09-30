from pathlib import Path
from typing import Optional, Union

import requests
import s3fs
import xarray as xr

from opera_disp_tms.tmp_s3_access import get_credentials


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


def open_opera_disp_product(s3_uri: str, dataset_path: Optional[str] = None):
    creds = get_credentials()
    s3_fs = s3fs.S3FileSystem(key=creds['accessKeyId'], secret=creds['secretAccessKey'], token='sessionToken')

    group = dict()
    if dataset_path:
        group['group'] = dataset_path

    ds = xr.open_dataset(
        s3_fs.open(s3_uri, **IO_PARAMS['fsspec_params']),
        engine='h5netcdf',
        **group,
        **IO_PARAMS['h5py_params'],
    )
    return ds

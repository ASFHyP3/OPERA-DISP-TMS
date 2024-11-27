from datetime import datetime
from typing import List, Tuple

import rioxarray  # noqa
import s3fs
import xarray as xr
from osgeo import osr

from opera_disp_tms.utils import DATE_FORMAT


IO_PARAMS = {
    'fsspec_params': {
        'skip_instance_cache': True,
        'cache_type': 'first',  # or "first" with enough space
        'block_size': 8 * 1024 * 1024,  # could be bigger
    },
    'h5py_params': {
        'driver_kwds': {  # only recent versions of xarray and h5netcdf allow this correctly
            'page_buf_size': 32 * 1024 * 1024,  # this one only works in repacked files
            'rdcc_nbytes': 8 * 1024 * 1024,  # this one is to read the chunks
        }
    },
}
S3_FS = s3fs.S3FileSystem()


def open_s3_xarray_dataset(url: str, group: str = '/') -> xr.Dataset:
    """Open an xarray hdf5/netcdf4 dataset from S3

    Args:
        url: URL of the dataset
        group: Group within the dataset to open
    """
    ds = xr.open_dataset(
        S3_FS.open(url, **IO_PARAMS['fsspec_params']), group=group, engine='h5netcdf', **IO_PARAMS['h5py_params']
    )
    return ds


def get_opera_disp_granule_metadata(url: str) -> Tuple:
    """Get metadata from an OPERA DISP granule

    Args:
        url: URL of the granule

    Returns:
        Tuple of reference point array, reference point geo, reference date, secondary date, frame_id, and EPSG
    """
    ds_metadata = open_s3_xarray_dataset(url, group='/corrections')

    row = int(ds_metadata['reference_point'].attrs['rows'])
    col = int(ds_metadata['reference_point'].attrs['cols'])

    easting = int(ds_metadata.x.values[col])
    northing = int(ds_metadata.y.values[row])
    ref_point_eastingnorthing = (easting, northing)

    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds_metadata['spatial_ref'].attrs['crs_wkt'])
    epsg = int(srs.GetAuthorityCode(None))

    reference_date = datetime.strptime(url.split('/')[-1].split('_')[6], DATE_FORMAT)
    secondary_date = datetime.strptime(url.split('/')[-1].split('_')[7], DATE_FORMAT)
    frame_id = int(url.split('/')[-1].split('_')[4][1:])

    return ref_point_eastingnorthing, epsg, reference_date, secondary_date, frame_id


def open_opera_disp_granule(url: str, data_vars=List[str]) -> xr.Dataset:
    """Open an OPERA DISP granule from S3 and set important attributes

    Args:
        url: URL of the granule
        data_vars: List of data variable names to include

    Returns:
        Dataset of the granule
    """
    ds = open_s3_xarray_dataset(url)
    data = ds[data_vars]
    data.rio.write_crs(ds['spatial_ref'].attrs['crs_wkt'], inplace=True)

    ref_point_eastingnorthing, _, reference_date, secondary_date, frame_id = get_opera_disp_granule_metadata(url)
    data.attrs['reference_point_eastingnorthing'] = ref_point_eastingnorthing
    data.attrs['reference_date'] = reference_date
    data.attrs['secondary_date'] = secondary_date
    data.attrs['frame_id'] = frame_id
    return data

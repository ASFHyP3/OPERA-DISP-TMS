from datetime import datetime
from typing import Tuple

import rioxarray  # noqa
import s3fs
import xarray as xr
from osgeo import osr

from opera_disp_tms.utils import DATE_FORMAT


IO_PARAMS = {
    'fsspec_params': {
        # "skip_instance_cache": True
        'cache_type': 'blockcache',  # or "first" with enough space
        'block_size': 8 * 1024 * 1024,  # could be bigger
    },
    'h5py_params': {
        'driver_kwds': {  # only recent versions of xarray and h5netcdf allow this correctly
            'page_buf_size': 16 * 1024 * 1024,  # this one only works in repacked files
            'rdcc_nbytes': 8 * 1024 * 1024,  # this one is to read the chunks
        }
    },
}
S3_FS = s3fs.S3FileSystem()


def open_s3_xarray_dataset(s3_uri: str, group: str = '/') -> xr.Dataset:
    """Open an xarray hdf5/netcdf4 dataset from S3

    Args:
        s3_uri: URI of the dataset on S3
        group: Group within the dataset to open
    """
    ds = xr.open_dataset(
        S3_FS.open(s3_uri, **IO_PARAMS['fsspec_params']), group=group, engine='h5netcdf', **IO_PARAMS['h5py_params']
    )
    return ds


def get_opera_disp_granule_metadata(s3_uri) -> Tuple:
    """Get metadata from an OPERA DISP granule

    Args:
        s3_uri: URI of the granule on S3

    Returns:
        Tuple of reference point array, reference point geo, reference date, secondary date, frame_id, and EPSG
    """
    ds_metadata = open_s3_xarray_dataset(s3_uri, group='/corrections')

    row = int(ds_metadata['reference_point'].attrs['rows'])
    col = int(ds_metadata['reference_point'].attrs['cols'])
    ref_point_array = (col, row)

    longitude = float(ds_metadata['reference_point'].attrs['longitudes'])
    latitude = float(ds_metadata['reference_point'].attrs['latitudes'])
    ref_point_geo = (longitude, latitude)

    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds_metadata['spatial_ref'].attrs['crs_wkt'])
    epsg = int(srs.GetAuthorityCode(None))

    reference_date = datetime.strptime(s3_uri.split('/')[-1].split('_')[6], DATE_FORMAT)
    secondary_date = datetime.strptime(s3_uri.split('/')[-1].split('_')[7], DATE_FORMAT)
    frame_id = int(s3_uri.split('/')[-1].split('_')[4][1:])

    return ref_point_array, ref_point_geo, epsg, reference_date, secondary_date, frame_id


def open_opera_disp_granule(s3_uri: str, data_var=str) -> xr.DataArray:
    """Open an OPERA DISP granule from S3 and set important attributes

    Args:
        s3_uri: URI of the granule on S3
        data_var: Name of the data variable to open

    Returns:
        DataArray of the granule
    """
    ds = open_s3_xarray_dataset(s3_uri)
    data = ds[data_var]
    data.rio.write_crs(ds['spatial_ref'].attrs['crs_wkt'], inplace=True)

    ref_point_array, ref_point_geo, _, reference_date, secondary_date, frame_id = get_opera_disp_granule_metadata(
        s3_uri
    )
    data.attrs['reference_point_array'] = ref_point_array
    data.attrs['reference_point_geo'] = ref_point_geo
    data.attrs['reference_date'] = reference_date
    data.attrs['secondary_date'] = secondary_date
    data.attrs['frame_id'] = frame_id
    return data

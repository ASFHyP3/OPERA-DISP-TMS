from datetime import datetime

import rioxarray  # noqa
import xarray as xr
from osgeo import osr

from opera_disp_tms.tmp_s3_access import get_temporary_s3_fs
from opera_disp_tms.utils import DATE_FORMAT


IO_PARAMS: dict[str, dict] = {
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


class s3_xarray_dataset:
    def __init__(self, s3_uri: str, group: str = '/'):
        self.s3_uri = s3_uri
        self.group = group

    def __enter__(self) -> xr.Dataset:
        self.s3_fs = get_temporary_s3_fs().open(self.s3_uri, **IO_PARAMS['fsspec_params'])
        self.ds = xr.open_dataset(self.s3_fs, group=self.group, engine='h5netcdf', **IO_PARAMS['h5py_params'])
        return self.ds

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ds.close()
        self.s3_fs.close()


def get_opera_disp_granule_metadata(s3_uri) -> tuple:
    """Get metadata from an OPERA DISP granule

    Args:
        s3_uri: URI of the granule on S3

    Returns:
        Tuple of reference point array, reference point geo, reference date, secondary date, frame_id, and EPSG
    """
    with s3_xarray_dataset(s3_uri, group='/corrections') as ds_metadata:
        row = int(ds_metadata['reference_point'].attrs['rows'])
        col = int(ds_metadata['reference_point'].attrs['cols'])

        easting = int(ds_metadata.x.values[col])
        northing = int(ds_metadata.y.values[row])
        ref_point_eastingnorthing = (easting, northing)

        srs = osr.SpatialReference()
        srs.ImportFromWkt(ds_metadata['spatial_ref'].attrs['crs_wkt'])
        epsg = int(srs.GetAuthorityCode(None))

    reference_date = datetime.strptime(s3_uri.split('/')[-1].split('_')[6], DATE_FORMAT)
    secondary_date = datetime.strptime(s3_uri.split('/')[-1].split('_')[7], DATE_FORMAT)
    frame_id = int(s3_uri.split('/')[-1].split('_')[4][1:])

    return ref_point_eastingnorthing, epsg, reference_date, secondary_date, frame_id


def open_opera_disp_granule(ds: xr.Dataset, s3_uri: str, data_vars: list[str]) -> xr.Dataset:
    """Open an OPERA DISP granule from S3 and set important attributes

    Args:
        ds: dataset
        s3_uri: URI of the granule on S3
        data_vars: List of data variable names to include

    Returns:
        Dataset of the granule
    """
    data = ds[data_vars]
    data.rio.write_crs(ds['spatial_ref'].attrs['crs_wkt'], inplace=True)

    ref_point_eastingnorthing, _, reference_date, secondary_date, frame_id = get_opera_disp_granule_metadata(s3_uri)
    data.attrs['reference_point_eastingnorthing'] = ref_point_eastingnorthing
    data.attrs['reference_date'] = reference_date
    data.attrs['secondary_date'] = secondary_date
    data.attrs['frame_id'] = frame_id
    return data

"""Generate a set tiles for the Global Seasonal Sentinel-1 Interferometric Coherence and Backscatter Data Set
See https://registry.opendata.aws/ebd-sentinel-1-global-coherence-backscatter/ for more details on the dataset
"""
from itertools import product
from pathlib import Path
from typing import Iterable

import boto3
from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import ClientError
from osgeo import gdal


gdal.UseExceptions()


S3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
SOURCE_S3 = 's3://sentinel-1-global-coherence-earthbigdata/data/tiles'
UPLOAD_S3 = 's3://opera-disp-tms-dev'


def create_coh_s3_path(lon: int, lat: int, coh_prod: str = 'summer_vv_COH12') -> str:
    """Create S3 path for a given lon, lat and coherence product
    Args:
        lon: longitude
        lat: latitude
        coh_prod: coherence product name

    Returns:
        str: S3 path
    """
    lon_prefix = 'E' if lon >= 0 else 'W'
    lat_prefix = 'N' if lat >= 0 else 'S'
    key = f'{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}'
    s3_path = f'{SOURCE_S3}/{key}/{key}_{coh_prod}.tif'
    return s3_path


def download_coh(s3_path: str) -> str:
    """Download coherence tile from S3
    Args:
        s3_path: S3 path

    Returns:
        s3_path if download was successfule
    """
    if not Path(s3_path.split('/')[-1]).exists():
        bucket = s3_path.split('/')[2]
        path = '/'.join(s3_path.split('/')[3:])
        try:
            S3.download_file(bucket, path, s3_path.split('/')[-1])
            print(f'Downloaded {s3_path}')
        except ClientError:
            print(f'{s3_path} not found')
            return
        return s3_path
    else:
        return s3_path


def create_coh_tile(bbox: Iterable[int], coh_prod: str = 'summer_vv_COH12', gtiff: bool = True) -> str:
    """Create a mosaic of coherence tiles for a given bounding box

    Args:
        bbox: bounding box [min_lon, min_lat, max_lon, max_lat]
        coh_prod: coherence product name
        gtiff: save as GeoTIFF or COG

    Returns:
        str: path to the mosaic
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    s3_paths = []
    for lon in range(min_lon, max_lon):
        for lat in range(min_lat, max_lat):
            s3_paths.append(create_coh_s3_path(lon, lat))

    s3_paths = [create_coh_s3_path(lon, lat) for lon, lat in product(range(min_lon, max_lon), range(min_lat, max_lat))]

    s3_paths = [download_coh(x) for x in s3_paths]
    names = [x.split('/')[-1] for x in s3_paths if x is not None]

    def lon_string(lon): return f'E{abs(lon):03d}' if lon >= 0 else f'W{abs(lon):03d}'
    def lat_string(lat): return f'N{abs(lat):02d}' if lat >= 0 else f'S{abs(lat):02d}'
    bbox_str = f'{lat_string(min_lat)}{lon_string(min_lon)}_{lat_string(max_lat)}{lon_string(max_lon)}'

    product_name = f'{coh_prod}_{bbox_str}'
    vrt_path = f'{product_name}.vrt'
    output_path = f'{product_name}.tif'

    if len(names) > 0:
        print('Building mosaic...')
        vrt = gdal.BuildVRT(vrt_path, names)
        vrt.FlushCache()
        vrt = None

        if gtiff:
            opts = ['TILED=YES', 'COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS']
            warp_options = gdal.WarpOptions(format='GTiff', dstSRS='EPSG:3857', xRes=30, yRes=30, creationOptions=opts)
        else:
            warp_options = gdal.WarpOptions(format='COG', dstSRS='EPSG:3857', xRes=30, yRes=30)
        gdal.Warp(output_path, vrt_path, options=warp_options)

        Path(vrt_path).unlink()
        for name in names:
            Path(name).unlink()
        print('Mosaic done')
    else:
        print('No tiles found')

    return output_path


def split_range(start_value: int, end_value: int, n: int) -> list:
    """Split a range into n parts
    Args:
        start_value: start of the range
        end_value: end of the range
        n: number of parts

    Returns:
        list of tuples with the ranges
    """
    step = (stop-start) // n
    offset = (stop-start) % n
    ranges = [(a, b) for (a, b) in zip(range(start, stop, step), range(start+step, stop-offset+step, step))]
    ranges[-1] = (ranges[-1][0], stop)
    return ranges


def create_coh_tile_set(
    bbox: Iterable[int], n_parts_lon: int = 1, n_parts_lat: int = 1, coh_prod: str = 'summer_vv_COH12'
) -> None:
    """Create a set of mosaics for a given bounding box

    Args:
        bbox: bounding box [min_lon, min_lat, max_lon, max_lat]
        n_parts_lon: number of parts to split the longitude range into
        n_parts_lat: number of parts to split the latitude range into
        coh_prod: coherence product name
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    lon_ranges = split_range(min_lon, max_lon, n_parts_lon)
    lat_ranges = split_range(min_lat, max_lat, n_parts_lat)
    lon_lat_bboxes = [(lon[0], lat[0], lon[1], lat[1]) for lon, lat in product(lon_ranges, lat_ranges)]
    output_paths = []
    for lon_lat_box in lon_lat_bboxes:
        output_path = create_coh_tile(lon_lat_box, coh_prod=coh_prod)
        output_paths.append(output_path)
    print('All mosaics complete')


def upload_tileset_s3(prefix: str = 'summer_vv_COH12_v2', wildcard: str = 'summer_vv_COH12') -> None:
    """Upload a set of files to S3
    Args:
        prefix: S3 prefix to upload files to
        wildcard: wildcard to filter files by
    """
    s3 = boto3.client('s3')
    files = list(Path.cwd().glob(f'{wildcard}*.tif'))
    for file in files:
        s3.upload_file(str(file), UPLOAD_S3.split('/')[-1], f'{prefix}/{file.name}')


if __name__ == '__main__':
    # Full North America: 6,148 tiles, 34 GB uncompressed, 24 compressed
    lon_lat_box = [-169, 14, -63, 72]
    output_paths = create_coh_tile_set(lon_lat_box, n_parts_lon=3, n_parts_lat=3)

    upload_tileset_s3()

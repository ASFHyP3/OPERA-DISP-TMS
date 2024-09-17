import json
import os
from itertools import product
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import ClientError
from osgeo import gdal


gdal.UseExceptions()


S3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
SOURCE_S3 = 's3://sentinel-1-global-coherence-earthbigdata/data/tiles'
UPLOAD_S3 = 's3://opera-disp-tms-dev'
MAPBOX_ACCOUNT = os.environ['MAPBOX_ACCOUNT']
MAPBOX_SOURCE_NAME = 'summer_vv_COH12'


def create_coh_s3_path(lon, lat, coh_prod='summer_vv_COH12'):
    lon_prefix = 'E' if lon >= 0 else 'W'
    lat_prefix = 'N' if lat >= 0 else 'S'
    key = f'{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}'
    s3_path = f'{SOURCE_S3}/{key}/{key}_{coh_prod}.tif'
    return s3_path


def download_coh(s3_path):
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


def create_coh_tile(min_lon, min_lat, max_lon, max_lat, coh_prod='summer_vv_COH12', suffix=None):
    s3_paths = []
    for lon in range(min_lon, max_lon):
        for lat in range(min_lat, max_lat):
            s3_paths.append(create_coh_s3_path(lon, lat))

    s3_paths = [create_coh_s3_path(lon, lat) for lon, lat in product(range(min_lon, max_lon), range(min_lat, max_lat))]

    s3_paths = [download_coh(x) for x in s3_paths]
    names = [x.split('/')[-1] for x in s3_paths if x is not None]

    product_name = coh_prod if suffix is None else f'{coh_prod}_{suffix}'
    vrt_path = f'{product_name}.vrt'
    output_path = f'{product_name}.tif'

    if len(names) > 0:
        print('Building mosaic...')
        vrt = gdal.BuildVRT(vrt_path, names)
        vrt.FlushCache()
        vrt = None

        # creation_opts = ['TILED=YES', 'COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS']
        # gdal.Translate(output_path, vrt_path, format='GTiff', creationOptions=creation_opts)
        # gdal.Translate(output_path, vrt_path, format='COG', creationOptions=['COMPRESS=LZW'])
        # gdal.Translate(f'{product_name}.mbtiles', vrt_path, format='MBTILES')
        # warp_options = gdal.WarpOptions(format='GTiff', dstSRS='EPSG:3857', xRes=30, yRes=30)
        warp_options = gdal.WarpOptions(format='COG', dstSRS='EPSG:3857', xRes=30, yRes=30)
        gdal.Warp(output_path, vrt_path, options=warp_options)

        Path(vrt_path).unlink()
        for name in names:
            Path(name).unlink()
        print('Mosaic done')
    else:
        print('No tiles found')

    return output_path


def split_range(start_value, end_value, n):
    step = (end_value - start_value) // n
    ranges = []
    for i in range(n):
        start = start_value + i * step
        end = start_value + (i + 1) * step
        ranges.append((start, end))
    return ranges


def create_coh_tile_set(min_lon, min_lat, max_lon, max_lat, n_parts_lon=1, n_parts_lat=1, coh_prod='summer_vv_COH12'):
    lon_ranges = split_range(min_lon, max_lon, n_parts_lon)
    lat_ranges = split_range(min_lat, max_lat, n_parts_lat)
    lon_lat_bboxes = [(lon[0], lat[0], lon[1], lat[1]) for lon, lat in product(lon_ranges, lat_ranges)]
    output_paths = []
    for i, lon_lat_box in enumerate(lon_lat_bboxes):
        output_path = create_coh_tile(*lon_lat_box, coh_prod=coh_prod, suffix=i + 1)
        output_paths.append(output_path)
    print('All mosaics complete')


def upload_tileset(coh_prod='summer_vv_COH12'):
    s3 = boto3.client('s3')
    files = list(Path.cwd().glob(f'{coh_prod}*.tif'))
    for file in files:
        s3.upload_file(str(file), UPLOAD_S3.split('/')[-1], f'{coh_prod}/{file.name}')


def create_template(minzoom=1, maxzoom=12, offset=0, scale=1, units='meters'):
    template = {
        'version': 1,
        'type': 'rasterarray',
        'sources': [{'uri': f'mapbox://tileset-source/{MAPBOX_ACCOUNT}/{MAPBOX_SOURCE_NAME}'}],
        'minzoom': minzoom,
        'maxzoom': maxzoom,
        'layers': {
            '12-Day Summber Coherence': {
                'tilesize': 256,
                'offset': offset,
                'scale': scale,
                'resampling': 'bilinear',
                'buffer': 1,
                'units': units,
            },
        },
    }
    with open('template.json', 'w') as f:
        f.write(json.dumps(template))


if __name__ == '__main__':
    # Full North America: 6,148 tiles, 34 GB uncompressed, 24 compressed
    lon_lat_box = [-169, 14, -63, 72]
    # lon_lat_box = [-119, 36, -115, 40]
    # output_paths = create_coh_tile_set(*lon_lat_box, n_parts_lon=5, n_parts_lat=5)
    upload_tileset()

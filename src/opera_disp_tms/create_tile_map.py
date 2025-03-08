import argparse
import json
import multiprocessing
import subprocess
import tempfile
from pathlib import Path

from osgeo import gdal, gdalconst, osr

from opera_disp_tms import utils
from opera_disp_tms.constants import SCALE_DICT, UNITS_DICT


gdal.UseExceptions()


def create_bounds_file(info: dict, measurement_type: str, output_folder: Path) -> None:
    """Generate file with the bounds and scale ranges of the newly created vrt

    Args:
        info: gdalinfo dict from vrt file
        measurement_type: Data measurement type to set scale_range and units
        output_folder: folder to write "extent.json"
    """
    units = UNITS_DICT[measurement_type]
    scale_range = SCALE_DICT[measurement_type]
    minx, miny = info['cornerCoordinates']['lowerLeft']
    maxx, maxy = info['cornerCoordinates']['upperRight']
    proj = osr.SpatialReference(info['coordinateSystem']['wkt'])

    sig_figs = 3

    extent = {
        'extent': [minx, miny, maxx, maxy],
        'EPSG': int(proj.GetAttrValue('AUTHORITY', 1)),
        'scale_range': {
            'range': [round(scale, sig_figs) for scale in scale_range],
            'units': units,
        },
    }

    if not output_folder.exists():
        output_folder.mkdir()

    with open(output_folder / 'extent.json', 'w') as outfile:
        json.dump(extent, outfile)


def create_tile_map(measurement_type: str, input_rasters: list[Path]) -> Path:
    """Generate a directory with small .png tiles from a list of rasters in a common projection, following the OSGeo
    Tile Map Service Specification, using gdal2tiles: https://gdal.org/en/latest/programs/gdal2tiles.html

    Args:
        measurement_type: Data measurement type to set scale_range and output folder
        input_rasters: List of gdal-compatible raster paths to mosaic
    """
    scale_range = SCALE_DICT[measurement_type]
    output_dir = Path(measurement_type)

    with tempfile.NamedTemporaryFile() as mosaic_vrt, tempfile.NamedTemporaryFile() as byte_vrt:
        input_raster_strs = [str(raster) for raster in input_rasters]

        # mosaic the input rasters
        gdal.BuildVRT(mosaic_vrt.name, input_raster_strs, resampleAlg='nearest')
        vrt_info = gdal.Info(mosaic_vrt.name, format='json')

        gdal.Translate(
            destName=byte_vrt.name,
            srcDS=mosaic_vrt.name,
            format='VRT',
            outputType=gdalconst.GDT_Byte,
            scaleParams=[[*scale_range, 1, 255]],
            resampleAlg='nearest',
        )

        # create tile map
        command = [
            'gdal2tiles',
            '--xyz',
            '--zoom=2-11',
            f'--processes={multiprocessing.cpu_count()}',
            '--webviewer=openlayers',
            '--resampling=med',
            byte_vrt.name,
            str(output_dir),
        ]
        subprocess.run(command)

        # get bounds of VRT and write to file
        create_bounds_file(vrt_info, measurement_type, output_dir)

        return output_dir


def download_geotiffs(bucket: str, bucket_prefix: str, dest_dir: Path = Path('.')) -> list[Path]:
    resp = utils.list_files_in_s3(bucket, bucket_prefix)

    geotiff_s3_filenames = [f['Key'] for f in resp if f['Key'].endswith('.tif')]

    geotiff_paths = [
        utils.download_file_from_s3(bucket, geotiff_s3_filename, dest_dir)
        for geotiff_s3_filename in geotiff_s3_filenames
    ]

    return geotiff_paths


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Generate a directory with small.png tiles from a list of rasters in a common projection, '
        'following the OSGeo Tile Map Service Specification, using gdal2tiles: '
        'https://gdal.org/en/latest/programs/gdal2tiles.html'
    )

    parser.add_argument(
        'measurement_type',
        type=str,
        choices=['displacement', 'secant_velocity', 'velocity'],
        help='Data measurement to compute',
    )

    parser.add_argument('--bucket', help='AWS S3 bucket HyP3 uses for uploading the final products')
    parser.add_argument('--bucket-prefix', default='', help='Add a bucket prefix to products')

    return parser


def main():
    parser = make_parser()
    args = parser.parse_args()

    geotiff_paths = download_geotiffs(args.bucket, args.bucket_prefix)

    frame_ids = {utils.get_frame_id(str(geotiff)) for geotiff in geotiff_paths}
    direction = utils.get_common_direction(frame_ids)
    geotiff_paths.sort(key=lambda x: utils.get_west_most_point(str(x)), reverse=direction == 'DESCENDING')

    upload_path = create_tile_map(args.measurement_type, geotiff_paths)

    if args.bucket:
        output_s3_prefix = f'{args.bucket_prefix}/tms/'
        utils.upload_dir_to_s3(upload_path, args.bucket, output_s3_prefix)


if __name__ == '__main__':
    main()

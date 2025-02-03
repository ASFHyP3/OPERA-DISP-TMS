import argparse
import json
import multiprocessing
import subprocess
import tempfile
from pathlib import Path

from osgeo import gdal, gdalconst, osr

from opera_disp_tms.utils import download_file_from_s3, list_files_in_s3, upload_dir_to_s3


gdal.UseExceptions()


def create_bounds_file(info: dict, scale_range: list, output_folder: Path) -> None:
    """Generate file with the bounds and scale ranges of the newly created vrt

    Args:
        info: gdalinfo dict from vrt file
        scale_range: list with min and max of tile map
        output_folder: folder to write "extent.json"
    """
    minx, miny = info['cornerCoordinates']['lowerLeft']
    maxx, maxy = info['cornerCoordinates']['upperRight']
    proj = osr.SpatialReference(info['coordinateSystem']['wkt'])

    sig_figs = 3

    extent = {
        'extent': [minx, miny, maxx, maxy],
        'EPSG': int(proj.GetAttrValue('AUTHORITY', 1)),
        'scale_range': {
            'range': [round(scale, sig_figs) for scale in scale_range],
            'units': 'm/yr',
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
        output_folder: Path of the output directory to create
        input_rasters: List of gdal-compatible raster paths to mosaic
        scale_range: Optional list of two integers to scale the mosaic by
    """


    output_folder = measurement_type

    with tempfile.NamedTemporaryFile() as mosaic_vrt, tempfile.NamedTemporaryFile() as byte_vrt:
        # mosaic the input rasters
        gdal.BuildVRT(mosaic_vrt.name, input_rasters, resampleAlg='nearest')

        # scale the mosaic from Float to Byte
        vrt_info = gdal.Info(mosaic_vrt.name, stats=True, format='json')
        stats = vrt_info['bands'][0]['metadata']['']

        if measurement_type == 'displacement':
            scale_range = [float(stats['STATISTICS_MINIMUM']), float(stats['STATISTICS_MAXIMUM'])]
        else:
            scale_range = [-0.05, 0.05]

        gdal.Translate(
            destName=byte_vrt.name,
            srcDS=mosaic_vrt.name,
            format='VRT',
            outputType=gdalconst.GDT_Byte,
            scaleParams=[scale_range],
            resampleAlg='nearest',
        )

        # create tile map
        command = [
            'gdal2tiles',
            '--xyz',
            '--zoom=2-11',
            f'--processes={multiprocessing.cpu_count()}',
            '--webviewer=openlayers',
            '--resampling=near',
            byte_vrt.name,
            output_folder,
        ]
        subprocess.run(command)
        output_path = Path(output_folder)

        # get bounds of VRT and write to file
        create_bounds_file(vrt_info, scale_range, output_path)

        return output_path


def download_geotiffs(bucket: str, bucket_prefix: str) -> list[Path]:
    resp = list_files_in_s3(bucket, bucket_prefix)

    geotiff_s3_filenames = [f['Key'] for f in resp if f['Key'].endswith('.tif')]
    dest_dir = Path.cwd()

    geotiff_paths = [
        download_file_from_s3(bucket, geotiff_s3_filename, dest_dir) for geotiff_s3_filename in geotiff_s3_filenames
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

    upload_path = create_tile_map(args.measurement_type, geotiff_paths)

    if args.bucket:
        output_s3_prefix = f'{args.bucket_prefix}/tms/'

        upload_dir_to_s3(upload_path, args.bucket, output_s3_prefix)


if __name__ == '__main__':
    main()

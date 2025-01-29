import argparse
import json
import multiprocessing
import subprocess
import tempfile
from pathlib import Path

from osgeo import gdal, gdalconst, osr

from opera_disp_tms.utils import upload_dir_to_s3


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


def create_tile_map(output_folder: str, input_rasters: list[str], scale_range: list[float] | None = None) -> None:
    """Generate a directory with small .png tiles from a list of rasters in a common projection, following the OSGeo
    Tile Map Service Specification, using gdal2tiles: https://gdal.org/en/latest/programs/gdal2tiles.html

    Args:
        output_folder: Path of the output directory to create
        input_rasters: List of gdal-compatible raster paths to mosaic
        scale_range: Optional list of two integers to scale the mosaic by
    """
    with tempfile.NamedTemporaryFile() as mosaic_vrt, tempfile.NamedTemporaryFile() as byte_vrt:
        # mosaic the input rasters
        gdal.BuildVRT(mosaic_vrt.name, input_rasters, resampleAlg='nearest')

        # scale the mosaic from Float to Byte
        vrt_info = gdal.Info(mosaic_vrt.name, stats=True, format='json')
        stats = vrt_info['bands'][0]['metadata']['']

        if scale_range is None:
            scale_range = [float(stats['STATISTICS_MINIMUM']), float(stats['STATISTICS_MAXIMUM'])]

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

        # get bounds of VRT and write to file
        create_bounds_file(vrt_info, scale_range, Path(output_folder))


def download_geotiffs():
    pass


def generate_tile_map_service(measurement_type: str, frame_id: list[int]) -> Path:
    measurement_geotiffs = []

    download_geotiffs()

    scale = {
        'displacement': None,
        'secant_velocity': [-0.05, 0.05],
        'velocity': [-0.05, 0.05],
    }

    create_tile_map(measurement_type, measurement_geotiffs, scale[measurement_type])
    return Path(measurement_type)


def make_parser():
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

    parser.add_argument('--bucket', help='AWS S3 bucket HyP3 for upload the final products')
    parser.add_argument('--bucket-prefix', default='', help='Add a bucket prefix to products')

    return parser


def main():
    parser = make_parser()

    args = parser.parse_args()

    generate_tile_map_service(
        args.measurement_type,
        args.frame_id,
    )

    if args.bucket:
        upload_path = Path(args.measurement_type)
        upload_dir_to_s3(upload_path, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()

import argparse
import json
import multiprocessing
import subprocess
import tempfile
from pathlib import Path

from osgeo import gdal, gdalconst, osr


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
    extent = {
        'extent': [minx, miny, maxx, maxy],
        'EPSG': int(proj.GetAttrValue('AUTHORITY', 1)),
        'scale_range': {'range': scale_range, 'units': 'm/yr'},
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
            scale_range = [stats['STATISTICS_MINIMUM'], stats['STATISTICS_MAXIMUM']]

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


def main():
    parser = argparse.ArgumentParser(
        description='Generate a directory with small .png tiles from a list of rasters in a common projection, '
        'following the OSGeo Tile Map Service Specification, using gdal2tiles: '
        'https://gdal.org/en/latest/programs/gdal2tiles.html'
    )
    parser.add_argument('output_folder', type=str, help='Path of the output directory to create')
    parser.add_argument('input_rasters', type=str, nargs='+', help='List of gdal-compatible raster paths to mosaic')
    args = parser.parse_args()

    create_tile_map(args.output_folder, args.input_rasters)


if __name__ == '__main__':
    main()

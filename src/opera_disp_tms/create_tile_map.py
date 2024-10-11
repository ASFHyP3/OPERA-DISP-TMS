import argparse
import json
import multiprocessing
import subprocess
import tempfile
from pathlib import Path

from osgeo import gdal, gdalconst, osr

gdal.UseExceptions()


def get_tile_bounds(info: dict, output_folder: Path) -> None:
    """Generate file with the bounds of the newly created vrt
        Will return a file with: {"extent": [minx, miny, maxx, maxy], "EPSG": %EPSG}

    Args:
        info: gdalinfo dict from vrt file
        output_folder: folder to write "bounds.json"
    """
    minx, miny = info['cornerCoordinates']['lowerLeft']
    maxx, maxy = info['cornerCoordinates']['upperRight']
    proj = osr.SpatialReference(info['coordinateSystem']['wkt'])
    bounds = {
        "BOUNDS": [minx, miny, maxx, maxy],
        "EPSG": int(proj.GetAttrValue('AUTHORITY', 1))
    }

    with open(output_folder + '/bounds.json', 'w') as outfile:
        json.dump(bounds, outfile)
    return


def create_tile_map(output_folder: str, input_rasters: list[str]):
    """Generate a directory with small .png tiles from a list of rasters in a common projection, following the OSGeo
    Tile Map Service Specification, using gdal2tiles: https://gdal.org/en/latest/programs/gdal2tiles.html

    Args:
        output_folder: Path of the output directory to create
        input_rasters: List of gdal-compatible raster paths to mosaic
    """
    with tempfile.NamedTemporaryFile() as mosaic_vrt, tempfile.NamedTemporaryFile() as byte_vrt:
        # mosaic the input rasters
        gdal.BuildVRT(mosaic_vrt.name, input_rasters, resampleAlg='nearest')

        # scale the mosaic from Float to Byte
        stats = gdal.Info(mosaic_vrt.name, stats=True, format='json')['bands'][0]['metadata']['']

        # get bounds of VRT and write to file
        get_tile_bounds(stats, Path(output_folder))

        gdal.Translate(
            destName=byte_vrt.name,
            srcDS=mosaic_vrt.name,
            format='VRT',
            outputType=gdalconst.GDT_Byte,
            scaleParams=[[stats['STATISTICS_MINIMUM'], stats['STATISTICS_MAXIMUM']]],
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

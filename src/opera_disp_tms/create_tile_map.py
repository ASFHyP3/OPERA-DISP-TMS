import argparse
import multiprocessing
import subprocess
import tempfile

from osgeo import gdal, gdalconst


gdal.UseExceptions()


def create_tile_map(output_folder: str, input_rasters: list[str]):
    """Generate a directory with small .png tiles from a list of rasters in a common projection, following the OSGeo
    Tile Map Service Specification, using gdal2tiles: https://gdal.org/en/latest/programs/gdal2tiles.html

    Args:
        output_folder: Path of the output directory to create
        input_rasters: List of gdal-compatible raster paths to mosaic
    """
    with tempfile.NamedTemporaryFile() as mosaic_vrt, tempfile.NamedTemporaryFile() as byte_vrt:
        # mosaic input rasters
        gdal.BuildVRT(mosaic_vrt.name, input_rasters)

        # scale mosaic from Float to Byte
        gdal.Translate(
            destName=byte_vrt.name,
            srcDS=mosaic_vrt.name,
            format='VRT',
            outputType=gdalconst.GDT_Byte,
            scaleParams=[[]],
        )

        # create tile map
        command = [
            'gdal2tiles',
            # '--xyz', # FIXME https://github.com/OSGeo/gdal/issues/10356
            '--zoom=2-11',
            f'--processes={multiprocessing.cpu_count()}',
            byte_vrt.name,
            output_folder,
        ]
        subprocess.run(command)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate a directory with small .png tiles from a list of rasters in a common projection, '
                    'following the OSGeo Tile Map Service Specification, using gdal2tiles: '
                    'https://gdal.org/en/latest/programs/gdal2tiles.html'
    )
    parser.add_argument('output_folder', type=str, help='Path of the output directory to create')
    parser.add_argument('input_rasters', type=str, nargs='+', help='List of gdal-compatible raster paths to mosaic')
    args = parser.parse_args()

    create_tile_map(args.output_folder, args.input_rasters)

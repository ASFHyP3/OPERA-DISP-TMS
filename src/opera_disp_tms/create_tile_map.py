import argparse
import multiprocessing
import subprocess
import tempfile

from osgeo import gdal, gdalconst


gdal.UseExceptions()


def create_tile_map(output_folder: str, input_rasters: list[str]):
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
    parser = argparse.ArgumentParser()
    parser.add_argument('output_folder', type=str)
    parser.add_argument('input_rasters', type=str, nargs='+')
    args = parser.parse_args()

    create_tile_map(args.output_folder, args.input_rasters)

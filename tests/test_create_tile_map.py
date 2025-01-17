import json

import numpy as np
from osgeo import gdal, osr

from opera_disp_tms import create_tile_map


def create_test_geotiff(output_file, geotransform, shape, epsg):
    driver = gdal.GetDriverByName('GTiff')
    dataset = driver.Create(output_file, shape[1], shape[0], 1, gdal.GDT_Byte)
    dataset.SetGeoTransform(geotransform)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.WriteArray(np.ones(shape, dtype=int))
    dataset = None


def test_create_bounds_file(tmp_path):
    epsg = 3857
    minx, miny, maxx, maxy = [-113, 33, -112, 34]
    geotransform = [minx, 0.1, 0, maxy, 0, -0.01]
    shape = (100, 10)
    frame_tile = tmp_path / 'test_tile.tif'
    scale_range = [0.0001112315, 1]

    create_test_geotiff(str(frame_tile), geotransform, shape, epsg)

    info = gdal.Info(str(frame_tile), format='json')
    create_tile_map.create_bounds_file(info, scale_range, tmp_path)

    with open(f'{tmp_path}/extent.json') as f:
        extent_json = json.load(f)
        print(extent_json)

    assert extent_json == {
        'extent': [minx, miny, maxx, maxy],
        'scale_range': {'range': [0.0001, 1], 'units': 'm/yr'},
        'EPSG': epsg,
    }

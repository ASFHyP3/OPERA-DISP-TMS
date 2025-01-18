import json

import numpy as np
import pytest
from osgeo import gdal, osr

from opera_disp_tms import create_tile_map


def test_create_bounds_file(tmp_path, geotiff_info):
    scale_range = [-1, 1]

    create_tile_map.create_bounds_file(geotiff_info, scale_range, tmp_path)

    with open(f'{tmp_path}/extent.json') as f:
        extent_json = json.load(f)
        print(extent_json)

    assert extent_json == {
        'extent': [-113, 33, -112, 34],
        'scale_range': {'range': [-1, 1], 'units': 'm/yr'},
        'EPSG': 3857,
    }


def test_bounds_file_scale_is_rounded(tmp_path, geotiff_info):
    scale_range = [-0.064441680908203, 0.051021575927734]

    create_tile_map.create_bounds_file(geotiff_info, scale_range, tmp_path)

    with open(f'{tmp_path}/extent.json') as f:
        extent_json = json.load(f)
        print(extent_json)

    assert extent_json['scale_range']['range'] == [-0.0644, 0.0510]


@pytest.fixture
def geotiff_info(tmp_path):
    epsg = 3857
    minx, _, _, maxy = [-113, 33, -112, 34]
    geotransform = [minx, 0.1, 0, maxy, 0, -0.01]
    shape = (100, 10)
    frame_tile = tmp_path / 'test_tile.tif'

    create_test_geotiff(str(frame_tile), geotransform, shape, epsg)

    info = gdal.Info(str(frame_tile), format='json')

    return info


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

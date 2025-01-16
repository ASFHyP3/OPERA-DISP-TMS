"""Test functions in generate_metadata_tile.py"""

from collections import namedtuple

import numpy as np
import pytest
from osgeo import gdal
from shapely.geometry import Polygon, box

from opera_disp_tms import generate_metadata_tile
from opera_disp_tms.frames import Frame


gdal.UseExceptions()


def test_create_product_name():
    name = generate_metadata_tile.create_product_name(['ONE', 'TWO'], 'ASC', (1, 2, 3, 4))
    assert name == 'ONE_TWO_ASC_E001N04'

    name = generate_metadata_tile.create_product_name(['ONE', 'TWO'], 'ASC', (-4, -3, -2, -1))
    assert name == 'ONE_TWO_ASC_W004S01'


def test_reorder_frames():
    Geom = namedtuple('Geom', ['bounds'])
    StubFrame = namedtuple('StubFrame', ['relative_orbit_number', 'frame_id', 'geom', 'orbit_pass'])

    frame_asc = StubFrame(1, 1, Geom([0, 0, 1, 1]), 'ASC')
    frame_des = StubFrame(1, 1, Geom([0, 0, 1, 1]), 'DES')
    with pytest.raises(ValueError):
        generate_metadata_tile.reorder_frames([frame_asc, frame_des], add_first='min_frame_number')  # type: ignore[list-item]

    frame_1_1 = StubFrame(1, 1, Geom([2, 1, 4, 3]), 'ASC')
    frame_1_2 = StubFrame(1, 2, Geom([4, 3, 6, 5]), 'ASC')
    frame_2_3 = StubFrame(2, 3, Geom([0, 0, 2, 2]), 'ASC')
    frame_2_4 = StubFrame(2, 4, Geom([2, 2, 4, 4]), 'ASC')

    result = generate_metadata_tile.reorder_frames(
        [frame_2_4, frame_1_2, frame_2_3, frame_1_1], add_first='min_frame_number'  # type: ignore[list-item]
    )
    assert result == [frame_2_4, frame_2_3, frame_1_2, frame_1_1]  # type: ignore[comparison-overlap]

    result = generate_metadata_tile.reorder_frames([frame_2_4, frame_1_2, frame_2_3, frame_1_1], add_first='west_most')  # type: ignore[list-item]
    assert result == [frame_2_4, frame_2_3, frame_1_2, frame_1_1]  # type: ignore[comparison-overlap]

    result = generate_metadata_tile.reorder_frames([frame_2_4, frame_1_2, frame_2_3, frame_1_1], add_first='east_most')  # type: ignore[list-item]
    assert result == [frame_1_2, frame_1_1, frame_2_4, frame_2_3]  # type: ignore[comparison-overlap]

    frame_1_anti = StubFrame(1, 1, Geom([-1, -1, 1, 1]), 'ASC')
    frame_2_norm = StubFrame(2, 1, Geom([0, 0, 2, 2]), 'ASC')
    result = generate_metadata_tile.reorder_frames([frame_1_anti, frame_2_norm], add_first='east_most')  # type: ignore[list-item]
    assert result == [frame_2_norm, frame_1_anti]  # type: ignore[comparison-overlap]


def test_create_empty_tile_frame(tmp_path):
    test_tif = tmp_path / 'test.tif'
    generate_metadata_tile.create_empty_frame_tile((1, 1, 2, 2), test_tif)
    assert test_tif.exists()

    info = gdal.Info(str(test_tif), options=['-json'])
    assert info['driverShortName'] == 'GTiff'
    assert info['metadata']['IMAGE_STRUCTURE']['COMPRESSION'] == 'LZW'
    assert 'ID["EPSG",3857]' in info['coordinateSystem']['wkt']
    assert info['wgs84Extent']
    lat_lon_bounds = Polygon(info['wgs84Extent']['coordinates'][0]).bounds
    assert np.isclose(lat_lon_bounds, [1, 1, 2, 2], rtol=1e-4).all()


def test_burn_frame(tmp_path):
    frame1 = Frame(9999, 1, 1, 'ASCENDING', True, True, box(1, 1, 2, 1.5))

    test_tif = tmp_path / 'test.tif'
    generate_metadata_tile.create_empty_frame_tile((1, 1, 2, 2), test_tif)

    generate_metadata_tile.burn_frame(frame1, test_tif)

    ds = gdal.Open(str(test_tif))
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()
    ds = None

    golden = np.zeros(data.shape)
    golden[int(data.shape[0] / 2) :, :] = 9999
    assert np.all(data == golden)

    frame2 = Frame(10000, 1, 1, 'ASCENDING', True, True, box(1, 1, 1.5, 2))
    generate_metadata_tile.burn_frame(frame2, test_tif)

    ds = gdal.Open(str(test_tif))
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()
    ds = None

    golden[:, : int(data.shape[0] / 2) - 1] = 10000
    assert np.all(data == golden)

from datetime import datetime

from osgeo import gdal

from opera_disp_tms.generate_sw_disp_tile import frames_from_metadata


def test_frames_from_metadata(tmp_path):
    tmp_tif = tmp_path / 'test.tif'
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(tmp_tif, 1, 1, 1, gdal.GDT_Byte)
    ds.SetMetadata(
        {
            'OPERA_FRAMES': '1, 2',
            'FRAME_1_REF_TIME': '20210101T000000Z',
            'FRAME_1_REF_POINT_ARRAY': '1, 2',
            'FRAME_1_REF_POINT_GEO': '1.0, 2.0',
            'FRAME_2_REF_TIME': '20210102T000000Z',
            'FRAME_2_REF_POINT_ARRAY': '3, 4',
            'FRAME_2_REF_POINT_GEO': '3.0, 4.0',
        }
    )
    ds = None
    frames = frames_from_metadata(tmp_tif)
    assert len(frames) == 2
    assert frames[0].frame == 1
    assert frames[0].reference_date == datetime(2021, 1, 1, 0, 0, 0)
    assert frames[0].reference_point_array == (1, 2)
    assert frames[0].reference_point_geo == (1.0, 2.0)
    assert frames[1].frame == 2
    assert frames[1].reference_date == datetime(2021, 1, 2, 0, 0, 0)
    assert frames[1].reference_point_array == (3, 4)
    assert frames[1].reference_point_geo == (3.0, 4.0)

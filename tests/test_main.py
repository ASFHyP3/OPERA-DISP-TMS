import argparse
from datetime import datetime
from unittest.mock import patch

import pytest

import opera_disp_tms.__main__ as main


def test_date():
    parser = argparse.ArgumentParser()
    parser.add_argument('date', type=str, action=main.Date)

    args = parser.parse_args(['20200101'])
    assert args.date == datetime(2020, 1, 1)

    args = parser.parse_args(['20241211'])
    assert args.date == datetime(2024, 12, 11)

    with pytest.raises(SystemExit):
        parser.parse_args(['2020010'])

    with pytest.raises(SystemExit):
        parser.parse_args(['2020-01-01'])

    with pytest.raises(SystemExit):
        parser.parse_args(['20201301'])


def test_frame():
    parser = argparse.ArgumentParser()
    parser.add_argument('frames', type=str.split, nargs='+', action=main.Frames)

    args = parser.parse_args(['1 2 3 4'])
    assert args.frames == [1, 2, 3, 4]

    args = parser.parse_args(['1', '2', '3', '4'])
    assert args.frames == [1, 2, 3, 4]

    args = parser.parse_args(['1 2', '3', '4'])
    assert args.frames == [1, 2, 3, 4]

    args = parser.parse_args(['1 46986'])
    assert args.frames == [1, 46986]

    test_cases = [
        ['0'],
        ['0 1 2'],
        ['46987'],
        ['46985 46986 46987'],
        ['foo'],
        ['1.1'],
    ]
    for test_case in test_cases:
        with pytest.raises(SystemExit):
            parser.parse_args(test_case)


def test_get_frame_id():
    info = {
        'metadata': {
            '': {
                'frame_id': '11113',
            },
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert main.get_frame_id('foo.tiff') == 11113
        mock_info.assert_called_once_with('foo.tiff', format='json')

    info = {
        'metadata': {
            '': {
                'frame_id': '321',
            },
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert main.get_frame_id('bar.tiff') == 321
        mock_info.assert_called_once_with('bar.tiff', format='json')


def test_get_west_most_point():
    info = {
        'wgs84Extent': {
            'type': 'Polygon',
            'coordinates': [
                [
                    [-122.201872, 41.1562811],
                    [-122.201872, 39.2490859],
                    [-118.7684233, 39.2490859],
                    [-118.7684233, 41.1562811],
                    [-122.201872, 41.1562811],
                ]
            ],
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert main.get_west_most_point('foo.tiff') == -122.201872
        mock_info.assert_called_once_with('foo.tiff', format='json')

    info = {
        'wgs84Extent': {
            'type': 'Polygon',
            'coordinates': [
                [
                    [176.4143837, 53.0448494],
                    [176.4418596, 50.8863044],
                    [-179.4626094, 50.8340006],
                    [-179.2889357, 52.9883554],
                    [176.4143837, 53.0448494],
                ]
            ],
        },
    }
    with patch('osgeo.gdal.Info', return_value=info) as mock_info:
        assert main.get_west_most_point('bar.tiff') == -179.4626094
        mock_info.assert_called_once_with('bar.tiff', format='json')


def test_get_common_direction():
    assert main.get_common_direction({1, 2, 3}) == 'ASCENDING'
    assert main.get_common_direction({1, 873, 46986}) == 'ASCENDING'
    assert main.get_common_direction({68, 69, 70}) == 'DESCENDING'
    with pytest.raises(ValueError):
        main.get_common_direction({67, 68})

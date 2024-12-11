import argparse
from datetime import datetime

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


def test_bbox():
    parser = argparse.ArgumentParser()
    parser.add_argument('bbox', type=str.split, nargs='+', action=main.Bbox)

    args = parser.parse_args(['1 1 1 1'])
    assert args.bbox == [1, 1, 1, 1]

    args = parser.parse_args(['1 2 3 4'])
    assert args.bbox == [1, 2, 3, 4]

    args = parser.parse_args(['1', '2', '3', '4'])
    assert args.bbox == [1, 2, 3, 4]

    args = parser.parse_args(['1 2', '3', '4'])
    assert args.bbox == [1, 2, 3, 4]

    args = parser.parse_args(['-180 -90 180 90'])
    assert args.bbox == [-180, -90, 180, 90]

    test_cases = [
        ['0 0 0'],
        ['0 0 0 0 0'],
        ['0.1 1 1 1'],
        ['1 0 0 0'],
        ['0 1 0 0'],
        ['-181 0 0 0'],
        ['0 0 181 0'],
        ['0 -91 0 0'],
        ['0 0 0 91'],
    ]
    for test_case in test_cases:
        with pytest.raises(SystemExit):
            parser.parse_args(test_case)

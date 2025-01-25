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

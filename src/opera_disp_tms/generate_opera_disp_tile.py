from datetime import datetime
from pathlib import Path

from opera_disp_tms.create_tile_map import create_tile_map
from opera_disp_tms.generate_metadata_tile import create_tile_for_bbox
from opera_disp_tms.generate_sw_disp_tile import create_sw_disp_tile
from opera_disp_tms.generate_sw_vel_tile import create_sw_vel_tile


def divide_bbox_into_tiles(bbox: list[int]) -> list[list[int]]:
    tiles = []
    for lon in range(bbox[0], bbox[2]):
        for lat in range(bbox[1], bbox[3]):
            tiles.append([lon, lat, lon + 1, lat + 1])
    return tiles


def generate_opera_disp_tile(
    tile_type: str, bbox: list[int], direction: str, begin_date: datetime, end_date: datetime
):
    metadata_path = create_tile_for_bbox(bbox, direction=direction)
    if not metadata_path:
        return

    if tile_type == 'displacement':
        out_path = create_sw_disp_tile(metadata_path, begin_date, end_date)
    elif tile_type == 'secant_velocity':
        out_path = create_sw_vel_tile(metadata_path, begin_date, end_date, minmax=True)
    else:
        raise ValueError(f'Unsupported tile type: {tile_type}')

    return out_path


def generate_opera_disp_tiles(
    tile_type: str, bbox: list[int], direction: str, begin_date: datetime, end_date: datetime
):
    tiles = []
    for tile_bbox in divide_bbox_into_tiles(bbox):
        tiles.append(generate_opera_disp_tile(tile_type, tile_bbox, direction, begin_date, end_date))

    scale = {
        'displacement': None,
        'secant_velocity': [-0.05, 0.05],
    }
    create_tile_map(tile_type, [str(x) for x in tiles], scale[tile_type])
    return Path(tile_type)

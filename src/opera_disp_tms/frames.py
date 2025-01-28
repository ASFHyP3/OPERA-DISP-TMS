import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import requests
from shapely import from_wkt
from shapely.geometry import Polygon


DB_PATH = Path(__file__).parent / 'opera-s1-disp-0.5.0.post1.dev20-2d.gpkg'


def download_file(url: str, download_path: Union[Path, str] = '.', chunk_size=10 * (2**20)):
    """Download a file without authentication.

    Args:
        url: URL of the file to download
        download_path: Path to save the downloaded file to
        chunk_size: Size to chunk the download into
    """
    session = requests.Session()

    with session.get(url, stream=True) as s:
        s.raise_for_status()
        with open(download_path, 'wb') as f:
            for chunk in s.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    session.close()


@dataclass
class Frame:
    frame_id: int
    relative_orbit_number: int
    orbit_pass: str
    geom: Polygon

    @classmethod
    def from_row(cls, row):
        return cls(
            frame_id=row[0],
            relative_orbit_number=row[1],
            orbit_pass=row[2],
            geom=from_wkt(row[3]),
        )


def download_frame_db(db_path: Path = DB_PATH) -> Path:
    """Download the OPERA burst database.
    Currently using a version created using opera-adt/burst_db v0.5.0, but hope to switch to ASF-provide source.

    Args:
        db_path: Path to save the database file to

    Returns:
        Path to the downloaded database
    """
    if db_path.exists():
        return db_path

    print('Downloading frame database...')
    url = f'https://opera-disp-tms-dev.s3.us-west-2.amazonaws.com/{db_path.name}'
    return download_file(url, db_path)


def get_frames(frame_ids: list[int]) -> list[Frame]:
    """Get a list of frame objects for given frame IDs.

    Args:
        frame_ids: A list of OPERA frame IDs to get orbit passes for.

    Returns:
        A list of Frame objects for the given frame IDs.
    """
    download_frame_db()
    query = (
        'SELECT fid as frame_id, relative_orbit_number, orbit_pass, ASText(GeomFromGPB(geom)) AS wkt '
        'FROM frames '
        'WHERE fid IN ({})'
    ).format(','.join('?' for _ in frame_ids))

    with sqlite3.connect(DB_PATH) as con:
        con.enable_load_extension(True)
        con.load_extension('mod_spatialite')
        cursor = con.cursor()
        cursor.execute(query, frame_ids)
        rows = cursor.fetchall()

    frames = [Frame.from_row(row) for row in rows]
    return frames


def reorder_frames(frame_ids: list[int]) -> list[int]:
    """Reorder a set of frames so that they overlap correctly when rasterized.
    Frames within a relative orbit are stacked so that higher frame numbers are on top (so they are rasterized first).
    Relative orbits sets are ordered from east to west for ascending, west to east for descending groups.

    Args:
        frame_ids: The list of frame ids to reorder

    Returns:
        The reordered list of frames
    """
    frame_list = get_frames(frame_ids)
    orbit_passes = list({x.orbit_pass for x in frame_list})
    if len(orbit_passes) > 1:
        raise ValueError('Cannot reorder frames with different orbit passes')
    add_first = 'east_most' if orbit_passes[0] == 'ASCENDING' else 'west_most'

    orbits = list({frame.relative_orbit_number for frame in frame_list})
    orbit_groups = {}
    for orbit in orbits:
        frames = [frame for frame in frame_list if frame.relative_orbit_number == orbit]
        frames = sorted(frames, key=lambda x: x.frame_id)
        min_x = min([x.geom.bounds[0] for x in frames])
        if min_x == -180:
            # In Anti-Meridian case, prioritize the relative orbit that goes the furthest north
            sort_metric = -180_000 + max([x.geom.bounds[3] for x in frames])
        else:
            sort_metric = min_x
        orbit_groups[orbit] = (sort_metric, frames)

    sorted_orbits = sorted(orbit_groups, key=lambda x: orbit_groups[x][0], reverse=add_first == 'east_most')
    sorted_frames = [frame for sublist in [orbit_groups[orbit][1] for orbit in sorted_orbits] for frame in sublist]
    sorted_frame_ids = [frame.frame_id for frame in sorted_frames]
    return sorted_frame_ids


def sort_geotiffs(geotiff_names: list[str]) -> list[str]:
    """Sort geotiffs by frame number

    Args:
        geotiff_names: List of geotiff file names

    Returns:
        List of geotiff file names sorted by frame number
    """
    frame_ids = [int(name.split('_')[1]) for name in geotiff_names]
    assert len(frame_ids) == len(set(frame_ids)), 'Duplicate frame numbers found'
    sorted_frame_ids = reorder_frames(frame_ids)
    sorted_geotiffs = []
    for frame_id in sorted_frame_ids:
        sorted_geotiffs.append([name for name in geotiff_names if int(name.split('_')[1]) == frame_id][0])
    return sorted_geotiffs

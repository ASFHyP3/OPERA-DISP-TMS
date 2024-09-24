import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Union

import requests
from shapely import from_wkt
from shapely.geometry import Polygon, box


DB_PATH = Path(__file__).parent / 'opera-s1-disp-0.5.0.post1.dev20-2d.gpkg'


@dataclass
class Frame:
    frame_id: int
    epsg: int
    relative_orbit_number: int
    orbit_pass: str
    is_land: bool
    is_north_america: bool
    geom: Polygon

    @classmethod
    def from_row(cls, row):
        return cls(
            frame_id=row[0],
            epsg=row[1],
            relative_orbit_number=row[2],
            orbit_pass=row[3],
            is_land=row[4],
            is_north_america=row[5],
            geom=from_wkt(row[6]),
        )


def download_file(
    url: str,
    download_path: Union[Path, str] = '.',
    chunk_size=10 * (2**20),
) -> Path:
    """Download a file without authentication.

    Args:
        url: URL of the file to download
        download_path: Path to save the downloaded file to
        chunk_size: Size to chunk the download into

    Returns:
        download_path: The path to the downloaded file
    """
    session = requests.Session()

    with session.get(url, stream=True) as s:
        s.raise_for_status()
        with open(download_path, 'wb') as f:
            for chunk in s.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
    session.close()


def download_frame_db() -> Path:
    """Download the OPERA burst database.
    Currently using a version created using opera-adt/burst_db v0.5.0, but hope to switch to ASF-provide source.

    Returns:
        Path to the downloaded database
    """
    if DB_PATH.exists():
        return DB_PATH

    print('Downloading frame database...')
    url = f'https://opera-disp-tms-dev.s3.us-west-2.amazonaws.com/{DB_PATH.name}'
    download_file(url, DB_PATH)


def intersect(
    bbox: Iterable[int],
    orbit_pass: Optional[str] = None,
    is_north_america: Optional[bool] = None,
    is_land: Optional[bool] = None,
) -> Iterable[Frame]:
    """Query for frames intersecting a given bounding box or WKT geometry, optionally filtering by orbit pass."""
    if orbit_pass and orbit_pass not in ['ASCENDING', 'DESCENDING']:
        raise ValueError('orbit_pass must be either "ASCENDING" or "DESCENDING"')

    download_frame_db()
    wkt_str = box(*bbox).wkt

    query = """
WITH given_geom AS (
    SELECT PolygonFromText(?, 4326) as g
),
BBox AS (
    SELECT
        MbrMinX(g) AS minx,
        MbrMaxX(g) AS maxx,
        MbrMinY(g) AS miny,
        MbrMaxY(g) AS maxy
    FROM given_geom
)

SELECT fid as frame_id, epsg, relative_orbit_number, orbit_pass,
       is_land, is_north_america, ASText(GeomFromGPB(geom)) AS wkt
FROM frames
WHERE fid IN (
    SELECT id
    FROM rtree_frames_geom
    JOIN BBox ON
        rtree_frames_geom.minx <= BBox.maxx AND
        rtree_frames_geom.maxx >= BBox.minx AND
        rtree_frames_geom.miny <= BBox.maxy AND
        rtree_frames_geom.maxy >= BBox.miny
)
AND Intersects((SELECT g FROM given_geom), GeomFromGPB(geom))
"""

    params = [wkt_str]
    if orbit_pass in ['ASCENDING', 'DESCENDING']:
        query += ' AND orbit_pass = ?'
        params.append(orbit_pass)

    if is_north_america is not None:
        query += ' AND is_north_america = ?'
        params.append(int(is_north_america))

    if is_land is not None:
        query += ' AND is_land = ?'
        params.append(int(is_land))

    with sqlite3.connect(DB_PATH) as con:
        con.enable_load_extension(True)
        con.load_extension('mod_spatialite')
        cursor = con.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    intersecting_frames = [Frame.from_row(row) for row in rows]
    return intersecting_frames

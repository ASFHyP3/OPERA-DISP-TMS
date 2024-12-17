import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from shapely import from_wkt
from shapely.geometry import Polygon, box

from opera_disp_tms.utils import download_file


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

    def to_geojson(self, out_path: Path) -> None:
        """Save frame geometry to a GeoJSON file.
        Keep all the attributes in the GeoJSON properties

        Args:
            out_path: Path to save the GeoJSON file to
        """
        geojson = {
            'type': 'Feature',
            'geometry': json.loads(self.geom.__geo_interface__),
            'properties': {
                'frame_id': self.frame_id,
                'epsg': self.epsg,
                'relative_orbit_number': self.relative_orbit_number,
                'orbit_pass': self.orbit_pass,
                'is_land': self.is_land,
                'is_north_america': self.is_north_america,
            },
        }
        with open(out_path, 'w') as f:
            json.dump(geojson, f)


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


def build_query(
    bbox: tuple[int, int, int, int],
    orbit_pass: str | None = None,
    is_north_america: bool | None = None,
    is_land: bool | None = None,
) -> tuple:
    """Build a query for identifying OPERA frames intersecting a given bounding box,
    optionally filtering by more fields.

    Args:
        bbox: Bounding box to query for
        orbit_pass: Filter by orbit pass (either 'ASCENDING' or 'DESCENDING')
        is_north_america: Filter by whether the frame intersects North America
        is_land: Filter by whether the frame intersects land

    Returns:
        Tuple with the query and parameters to pass to the query
    """
    wkt_str = box(*bbox).wkt
    query = (
        'WITH given_geom AS ( '
        '    SELECT PolygonFromText(?, 4326) as g '
        '), '
        'BBox AS ( '
        '    SELECT '
        '        MbrMinX(g) AS minx, '
        '        MbrMaxX(g) AS maxx, '
        '        MbrMinY(g) AS miny, '
        '        MbrMaxY(g) AS maxy '
        '    FROM given_geom '
        ') '
        'SELECT fid as frame_id, epsg, relative_orbit_number, orbit_pass, '
        '       is_land, is_north_america, ASText(GeomFromGPB(geom)) AS wkt '
        'FROM frames '
        'WHERE fid IN ( '
        '    SELECT id '
        '    FROM rtree_frames_geom '
        '    JOIN BBox ON '
        '        rtree_frames_geom.minx <= BBox.maxx AND '
        '        rtree_frames_geom.maxx >= BBox.minx AND '
        '        rtree_frames_geom.miny <= BBox.maxy AND '
        '        rtree_frames_geom.maxy >= BBox.miny '
        ') '
        'AND Intersects((SELECT g FROM given_geom), GeomFromGPB(geom))'
    )

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

    return query, params


def intersect(
    bbox: tuple[int, int, int, int],
    orbit_pass: str | None = None,
    is_north_america: bool | None = None,
    is_land: bool | None = None,
) -> Iterable[Frame]:
    """Query OPERA frame database to obtain frames intersecting a given bounding box,
    optionally filtering by more fields.

    Args:
        bbox: Bounding box to query for
        orbit_pass: Filter by orbit pass (either 'ASCENDING' or 'DESCENDING')
        is_north_america: Filter by whether the frame intersects North America
        is_land: Filter by whether the frame intersects land

    Returns:
        Iterable of Frame objects matching the input criteria
    """
    if orbit_pass and orbit_pass not in ['ASCENDING', 'DESCENDING']:
        raise ValueError('orbit_pass must be either "ASCENDING" or "DESCENDING"')

    download_frame_db()
    query, params = build_query(bbox, orbit_pass, is_north_america, is_land)
    with sqlite3.connect(DB_PATH) as con:
        con.enable_load_extension(True)
        con.load_extension('mod_spatialite')
        cursor = con.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    intersecting_frames = [Frame.from_row(row) for row in rows]
    return intersecting_frames


# FIXME: Remove when updating to OPERA DISP data v0.9
def get_orbit_pass(frame_id: int) -> str:
    """Get the orbit pass for an OPERA frame

    Args:
        frame_id: OPERA frame ID to get orbit pass for

    Returns:
        "ASCENDING" or "DESCENDING"
    """
    download_frame_db()
    query = (
        'SELECT fid as frame_id, epsg, relative_orbit_number, orbit_pass, '
        '       is_land, is_north_america, ASText(GeomFromGPB(geom)) AS wkt '
        'FROM frames '
        'WHERE fid = ?'
    )
    with sqlite3.connect(DB_PATH) as con:
        con.enable_load_extension(True)
        con.load_extension('mod_spatialite')
        cursor = con.cursor()
        cursor.execute(query, [int(frame_id)])
        rows = cursor.fetchall()

    assert len(rows) == 1
    frame = Frame.from_row(rows[0])
    return frame.orbit_pass

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np

from opera_disp_tms import utils
from opera_disp_tms.prep_stack import load_sw_disp_stack


def create_sw_disp_tile(frame_id: int, begin_date: datetime, end_date: datetime) -> Path:
    """Create a short wavelength cumulative displacement tile.
    Tile is generated using a set of granules whose secondary date are between `begin_date` and
    `end_date`. For each frame, the most recent granule is selected for the tile.

    Args:
        frame_id: FIXME
        begin_date: The start of the date range
        end_date: The end of the date range

    Returns:
        Path to the generated tile
    """
    product_name = utils.create_tile_name(frame_id, begin_date, end_date, prod_type='displacement')
    product_path = Path.cwd() / product_name

    data = load_sw_disp_stack(frame_id, begin_date, end_date, 'spanning')[-1]
    data.rio.write_nodata(np.nan, inplace=True)
    data = data.rio.reproject('EPSG:3857')
    data.rio.to_raster(product_path.name)
    return product_path


def main():
    """CLI entry point
    Example:
    generate_sw_disp_tile METADATA_ASCENDING_N42W124.tif 20170901 20171231
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('frame_id', type=int, help='FIXME')
    parser.add_argument(
        'begin_date', type=str, help='Start of date search range to generate tile for in format: %Y%m%d'
    )
    parser.add_argument('end_date', type=str, help='End of date search range to generate tile for in format: %Y%m%d')

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, '%Y%m%d')
    args.end_date = datetime.strptime(args.end_date, '%Y%m%d')

    create_sw_disp_tile(args.frame_id, args.begin_date, args.end_date)


if __name__ == '__main__':
    main()

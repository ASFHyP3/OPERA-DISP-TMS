import argparse
from datetime import datetime
from pathlib import Path

from osgeo import gdal


gdal.UseExceptions()


DATE_FORMAT = '%Y%m%dT%H%M%SZ'


def create_sw_disp_tile(begin_date, end_date, metadata_path):
    if not metadata_path.exists():
        raise FileNotFoundError(f'{metadata_path} does not exist')
    if begin_date > end_date:
        raise ValueError('Begin date must be before end date')

    info_dict = gdal.Info(str(metadata_path), options=['-json'])
    # identify_component_granules()
    # standardize_reference_date_and_location()
    # create_blank_tile()
    # assign_tile_values()
    # update_tile_metadata()


def main():
    """CLI entrpypoint
    Example: generate_sw_disp_tile metadata_N37W122_N38W121.tif --begin-date 20160701T000000Z --end-date 20240922T154629Z
    """
    parser = argparse.ArgumentParser(description='Create a short wavelength cumulative displacement tile')
    parser.add_argument('metadata_path', type=str, help='Path to the metadata GeoTiff file')
    parser.add_argument('--begin-date', type=str, help='Beginning of date range to generate tile for in format: %Y%m%d')
    parser.add_argument('--end-date', type=str, help='End of date range to generate tile for in format: %Y%m%d')

    args = parser.parse_args()
    args.metadata_path = Path(args.metadata_path)
    args.begin_date = datetime.strptime(args.begin_date, DATE_FORMAT)
    args.end_date = datetime.strptime(args.end_date, DATE_FORMAT)

    create_sw_disp_tile(args.bbox, ascending=args.ascending)


if __name__ == '__main__':
    main()

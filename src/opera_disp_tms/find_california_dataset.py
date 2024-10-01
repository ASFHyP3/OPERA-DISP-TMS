"""Find all OPERA L3 DISP S1 PROVISIONAL V0.4 granules created for California test dataset.
see https://github.com/nasa/opera-sds/issues/54 for dataset creation request.
"""
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

import asf_search as asf


DATE_FORMAT = '%Y%m%dT%H%M%SZ'

PROCESSING_START = datetime.strptime('20240917T173251Z', DATE_FORMAT)
PROCESSING_END = datetime.strptime('20240922T154629Z', DATE_FORMAT)
DATA_START = datetime.strptime('20160701T000000Z', DATE_FORMAT)
DATA_END = datetime.strptime('20180702T000000Z', DATE_FORMAT)

DES_FRAMES = [
    3325,
    3326,
    3327,
    3328,
    11112,
    11113,
    11114,
    11117,
    18901,
    18902,
    18903,
    18904,
    18905,
    26689,
    26690,
    26691,
    30711,
    30712,
    30713,
    30714,
    30715,
    30716,
    38499,
    38500,
    38501,
    38502,
    38503,
    38504,
    46288,
    46289,
    46290,
    46291,
]
ASC_FRAMES = [
    9154,
    9155,
    9156,
    9157,
    9158,
    9159,
    9160,
    16939,
    16940,
    16941,
    16942,
    16943,
    16944,
    16945,
    16946,
    24726,
    24727,
    24728,  # Data is not available for this frame
    28757,
    28758,
    28759,
    28760,
    36539,
    36540,
    36541,
    36544,
    36545,
    36546,
    44325,
    44326,
    44327,
    44328,
    44329,
]
CAL_FRAMES = sorted(ASC_FRAMES + DES_FRAMES)


@dataclass
class Granule:
    scene_name: str
    frame: int
    orbit_pass: str
    url: str
    s3_uri: str
    reference_date: datetime
    secondary_date: datetime
    creation_date: datetime

    @classmethod
    def from_search_result(cls, search_product: asf.ASFProduct) -> 'Granule':
        """Create a Granule object from an ASF search result.

        Args:
            search_product: The search result to create the Granule from.

        Returns:
            A Granule object created from the search result.
        """
        scene_name = search_product.properties['sceneName']
        frame = int(scene_name.split('_')[4][1:])
        if frame in ASC_FRAMES:
            orbit_pass = 'ASCENDING'
        elif frame in DES_FRAMES:
            orbit_pass = 'DESCENDING'
        else:
            orbit_pass = 'UNKNOWN'
        url_base = 'https://cumulus-test.asf.alaska.edu/RTC/OPERA-S1/OPERA_L3_DISP-S1_PROVISIONAL_V0'
        url = f'{url_base}/{scene_name}/{scene_name}.nc'
        s3_base = 's3://asf-cumulus-test-opera-products/OPERA_L3_DISP-S1_PROVISIONAL_V0'
        s3_uri = f'{s3_base}/OPERA_L3_DISP-S1_PROVISIONAL_V0/{scene_name}/{scene_name}.nc'
        reference_date = datetime.strptime(scene_name.split('_')[-4], DATE_FORMAT)
        secondary_date = datetime.strptime(scene_name.split('_')[-3], DATE_FORMAT)
        creation_date = datetime.strptime(scene_name.split('_')[-1], DATE_FORMAT)
        return cls(
            scene_name=scene_name,
            frame=frame,
            orbit_pass=orbit_pass,
            url=url,
            s3_uri=s3_uri,
            reference_date=reference_date,
            secondary_date=secondary_date,
            creation_date=creation_date,
        )

    @classmethod
    def from_tuple(cls, tup: Tuple) -> 'Granule':
        """Create a Granule object from a tuple.

        Args:
            tup: The tuple to create the Granule from.

        Returns:
            A Granule object created from the tuple.
        """
        name, frame, orbit_pass, url, s3_uri, reference_date, secondary_date, creation_date = tup
        return cls(
            scene_name=name,
            frame=int(frame),
            orbit_pass=orbit_pass,
            url=url,
            s3_uri=s3_uri,
            reference_date=datetime.strptime(reference_date, DATE_FORMAT),
            secondary_date=datetime.strptime(secondary_date, DATE_FORMAT),
            creation_date=datetime.strptime(creation_date, DATE_FORMAT),
        )

    def to_tuple(self):
        return (
            self.scene_name,
            self.frame,
            self.orbit_pass,
            self.url,
            self.s3_uri,
            datetime.strftime(self.reference_date, DATE_FORMAT),
            datetime.strftime(self.secondary_date, DATE_FORMAT),
            datetime.strftime(self.creation_date, DATE_FORMAT),
        )


def find_test_data(desired_version: str = '0.4') -> Granule:
    """Find all OPERA L3 DISP S1 PROVISIONAL granules created for a specific version.

    Args:
        desired_version: The version of the granules to search for.

    Returns:
        A list of granules that match the search criteria.
    """
    session = asf.ASFSession(edl_host='uat.urs.earthdata.nasa.gov')
    disp_opts = asf.ASFSearchOptions(
        session=session, host='cmr.uat.earthdata.nasa.gov', shortName='OPERA_L3_DISP-S1_PROVISIONAL_V0'
    )
    disp_opts.maxResults = None
    cmr_keywords = [('options[readable_granule_name][pattern]', 'true')]
    granule_name_wildcard = [f'*_v{desired_version}_*']
    granule_name_wildcard = ['*']
    results = asf.search(opts=disp_opts, cmr_keywords=cmr_keywords, granule_list=granule_name_wildcard)
    granules = [Granule.from_search_result(result) for result in results]
    return granules


def filter_restults_to_california_dataset(granules: Iterable[Granule]) -> List[Granule]:
    """Filter the search results to only include granules from the California test dataset.

    Args:
        results: The granules to filter.

    Returns:
        A list of granules that are part of the California test dataset.
    """
    desired_granules = []
    for granule in granules:
        reference_within_data_date_range = DATA_START <= granule.reference_date <= DATA_END
        secondary_within_data_date_range = DATA_START <= granule.secondary_date <= DATA_END
        within_data_date_range = reference_within_data_date_range and secondary_within_data_date_range
        within_processing_date_range = PROCESSING_START <= granule.creation_date <= PROCESSING_END
        desired_frame = granule.frame in CAL_FRAMES

        if within_data_date_range and within_processing_date_range and desired_frame:
            desired_granules.append(granule)

    return desired_granules


def generate_granule_file(granules: Iterable[Granule], out_path: Path) -> None:
    """Generate a CSV file containing the information for a set of granules.

    Args:
        granules: The granules to write to the file.
        out_path: The path to write the file to.
    """
    with open(out_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(
            ['SCENE_NAME', 'FRAME', 'ORBIT_PASS', 'URL', 'S3_URI', 'REFERENCE_DATE', 'SECONDARY_DATE', 'CREATION_DATE']
        )
        writer.writerows([granule.to_tuple() for granule in granules])


def read_granule_file(in_path: Path) -> List['Granule']:
    """Read a CSV file containing granule information.

    Args:
        in_path: The path to the file to read.

    Returns:
        A list of granules read from the file.
    """
    granules = []
    with open(in_path, mode='r', newline='') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            granules.append(Granule.from_tuple(row))
    return granules


def find_california_dataset() -> List[str]:
    """Find all OPERA L3 DISP S1 PROVISIONAL V0.4 granules created for California test dataset.

    Returns:
        A list of granules that are part of the California test dataset.
    """
    granule_list_path = Path(__file__).parent / 'california_dataset.csv'
    breakpoint()
    if not granule_list_path.exists():
        all_granules = find_test_data()
        desired_granules = filter_restults_to_california_dataset(all_granules)
        generate_granule_file(desired_granules, granule_list_path)
    granules = read_granule_file(granule_list_path)
    return granules


if __name__ == '__main__':
    find_california_dataset()

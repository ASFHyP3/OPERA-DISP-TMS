from dataclasses import dataclass
from datetime import datetime

import requests

from opera_disp_tms.utils import within_one_day

CMR_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


@dataclass(frozen=True)
class Granule:
    scene_name: str
    frame_id: int
    orbit_pass: str
    url: str
    s3_uri: str
    reference_date: datetime
    secondary_date: datetime
    creation_date: datetime

    @classmethod
    def from_umm(cls, umm: dict) -> 'Granule':
        """Create a Granule object from a UMM search result.

        Args:
            umm: UMM JSON for the granule

        Returns:
            A Granule object created from the search result.
        """
        scene_name = umm['meta']['native-id']

        attributes = umm['umm']['AdditionalAttributes']
        frame_id = int(next(att['Values'][0] for att in attributes if att['Name'] == 'FRAME_NUMBER'))
        orbit_pass = next(att['Values'][0] for att in attributes if att['Name'] == 'ASCENDING_DESCENDING')

        urls = umm['umm']['RelatedUrls']
        url = next(url['URL'] for url in urls if url['Type'] == 'GET DATA')
        s3_uri = next(url['URL'] for url in urls if url['Type'] == 'GET DATA VIA DIRECT ACCESS')

        reference_date = datetime.strptime(
            umm['umm']['TemporalExtent']['RangeDateTime']['BeginningDateTime'], CMR_DATE_FORMAT
        )
        secondary_date = datetime.strptime(
            umm['umm']['TemporalExtent']['RangeDateTime']['EndingDateTime'], CMR_DATE_FORMAT
        )
        creation_date = datetime.strptime(umm['umm']['DataGranule']['ProductionDateTime'], CMR_DATE_FORMAT)
        return cls(
            scene_name=scene_name,
            frame_id=frame_id,
            orbit_pass=orbit_pass,
            url=url,
            s3_uri=s3_uri,
            reference_date=reference_date,
            secondary_date=secondary_date,
            creation_date=creation_date,
        )

    def __eq__(self, other) -> bool:
        """
        Compare two granules to see if they are represent the same data
        Args:
            other: Granule object to compare

        Returns:
            bool: True if they are identical, False otherwise
        """
        if self.frame_id == other.frame_id:
            if within_one_day(self.reference_date, other.reference_date):
                if within_one_day(self.secondary_date, other.secondary_date):
                    return True
        return False


def get_cmr_metadata(
    frame_id: int,
    version: str = '0.9',
    cmr_endpoint='https://cmr.uat.earthdata.nasa.gov/search/granules.umm_json',
) -> list[dict]:
    """Find all OPERA L3 DISP S1 granules for a specific frame ID and minimum product version

    Args:
        frame_id: The frame ID to search for.
        version: The minimum version of the granules to search for.
        cmr_endpoint: The endpoint to query for granules.
    """
    cmr_parameters = {
        'short_name': 'OPERA_L3_DISP-S1_V1',
        'attribute[]': [f'int,FRAME_NUMBER,{frame_id}', f'float,PRODUCT_VERSION,{version},'],
        'page_size': 2000,
    }
    headers: dict = {}
    items = []

    while True:
        response = requests.post(cmr_endpoint, data=cmr_parameters, headers=headers)
        response.raise_for_status()
        items.extend(response.json()['items'])
        if 'CMR-Search-After' not in response.headers:
            break
        headers['CMR-Search-After'] = response.headers['CMR-Search-After']
    return items


def find_granules_for_frame(frame_id: int) -> list[Granule]:
    """Find all OPERA L3 DISP S1 PROVISIONAL granules for a specific frame ID."""
    umms = get_cmr_metadata(frame_id)
    granules = [Granule.from_umm(umm) for umm in umms]
    return granules


def eliminate_duplicates(granules: list[Granule]) -> list[Granule]:
    """
    Eliminate duplicate granules and return a list of granules over unique times
    Args:
        granules:

    Returns:
        granules: a list of unique granules
    """
    unique_granules = []
    for candidate in granules:
        duplicate = False
        for other in granules:
            if candidate == other and (candidate.creation_date < other.creation_date or candidate.creation_date == other.creation_date and other in unique_granules):
                duplicate = True
        if not duplicate:
            unique_granules.append(candidate)
    return unique_granules

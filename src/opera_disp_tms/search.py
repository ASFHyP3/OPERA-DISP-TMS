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

    def __members(self) -> tuple:
        return (
            self.frame_id,
            self.reference_date,
            self.secondary_date,
            self.creation_date,
        )

    def __eq__(self, other) -> bool:
        """
        Compare two granules to see if they are represent the same data
        Args:
            other: Granule object to compare

        Returns:
            bool: True if they are identical, False otherwise
        """
        if type(other) is type(self):
            return self.__members() == other.__members()
        else:
            return False

    def __hash__(self):
        return hash(self.__members())


def get_cmr_metadata(
    frame_id: int,
    cmr_endpoint='https://cmr.earthdata.nasa.gov/search/granules.umm_json',
) -> list[dict]:
    """Find all OPERA L3 DISP S1 granules for a specific frame ID and minimum product version

    Args:
        frame_id: The frame ID to search for.
        cmr_endpoint: The endpoint to query for granules.
    """
    cmr_parameters = {
        'short_name': 'OPERA_L3_DISP-S1_V1',
        'attribute[]': f'int,FRAME_NUMBER,{frame_id}',
        'page_size': '2000',
    }
    headers: dict = {}
    items = []

    while True:
        response = requests.get(cmr_endpoint, params=cmr_parameters, headers=headers)
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
    Remove equivalent granules, preferring the granule with the more recent creation date
    Args:
        granules: a list of granules

    Returns:
        granules: a list of unique granules
    """
    unique_granules = []

    for candidate in filter_identical(granules):
        redundant = any([is_redundant(candidate, other) for other in granules])

        if redundant:
            continue

        unique_granules.append(candidate)

    return unique_granules


def filter_identical(granules: list[Granule]) -> list[Granule]:
    return list(dict.fromkeys(granules))


def is_redundant(candidate: Granule, other: Granule) -> bool:
    return (
        candidate.frame_id == other.frame_id
        and within_one_day(candidate.reference_date, other.reference_date)
        and within_one_day(candidate.secondary_date, other.secondary_date)
        and candidate.creation_date < other.creation_date
    )

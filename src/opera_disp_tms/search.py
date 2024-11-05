"""Find all OPERA L3 DISP S1 PROVISIONAL V0.7 granules created for California test dataset.
see https://github.com/nasa/opera-sds/issues/54 for dataset creation request.
"""

from dataclasses import dataclass
from datetime import datetime

import requests


DATE_FORMAT = '%Y%m%dT%H%M%SZ'
CAL_START = datetime.strptime('20160701T000000Z', DATE_FORMAT)
CAL_END = datetime.strptime('20190702T000000Z', DATE_FORMAT)

CAL_DES_FRAMES = [
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
CAL_ASC_FRAMES = [
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
CAL_FRAMES = sorted(CAL_ASC_FRAMES + CAL_DES_FRAMES)


@dataclass
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
    def from_umm(cls, umm) -> 'Granule':
        """Create a Granule object from a UMM search result.

        Args:
            search_product: The search result to create the Granule from.

        Returns:
            A Granule object created from the search result.
        """
        scene_name = umm['meta']['native-id']
        attributes = umm['umm']['AdditionalAttributes']
        frame_id = int([x['Values'][0] for x in attributes if x['Name'] == 'FRAME_ID'][0])
        # TODO: can change when orbit direction is added to UMM
        if frame_id in CAL_ASC_FRAMES:
            orbit_pass = 'ASCENDING'
        elif frame_id in CAL_DES_FRAMES:
            orbit_pass = 'DESCENDING'
        else:
            orbit_pass = 'UNKNOWN'
        urls = umm['umm']['RelatedUrls']
        url = [x['URL'] for x in urls if x['Type'] == 'GET DATA'][0]
        s3_uri = [x['URL'] for x in urls if x['Type'] == 'GET DATA VIA DIRECT ACCESS'][0]
        reference_date = datetime.strptime(scene_name.split('_')[-4], DATE_FORMAT)
        secondary_date = datetime.strptime(scene_name.split('_')[-3], DATE_FORMAT)
        creation_date = datetime.strptime(scene_name.split('_')[-1], DATE_FORMAT)
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


def get_cmr_metadata(
    frame_id: int,
    version: float = 0.7,
    temporal_range=[CAL_START, CAL_END],
    cmr_endpoint='https://cmr.uat.earthdata.nasa.gov/search/granules.umm_json',
) -> list[dict]:
    """Find all OPERA L3 DISP S1 granules created for a specific frame ID, product version, and temporal range.

    Args:
        frame_id: The frame ID to search for.
        version: The version of the granules to search for.
        temporal_range: The temporal range to search for granules in.
        cmr_endpoint: The endpoint to query for granules.
    """
    cmr_parameters = {
        'provider_short_name': 'ASF',
        'short_name': 'OPERA_L3_DISP-S1_PROVISIONAL_V0',
        'attribute[]': [f'int,FRAME_ID,{frame_id}', f'float,PRODUCT_VERSION,{version}'],
        'temporal[]': ','.join([date.strftime('%Y-%m-%dT%H:%M:%SZ') for date in temporal_range]),
        'page_size': 2000,
    }
    response = requests.post(cmr_endpoint, data=cmr_parameters)
    response.raise_for_status()
    return response.json()['items']


def find_california_granules_for_frame(frame_id: int):
    """Find all OPERA L3 DISP S1 PROVISIONAL V0.7 California dataset granules created for a specific frame ID."""
    umms = get_cmr_metadata(frame_id)
    granules = [Granule.from_umm(umm) for umm in umms]
    return granules

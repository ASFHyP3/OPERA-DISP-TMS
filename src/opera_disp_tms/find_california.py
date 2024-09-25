"""Find all OPERA L3 DISP S1 PROVISIONAL V0.4 granules created for California test dataset.
see https://github.com/nasa/opera-sds/issues/54 for dataset creation request.
"""
from datetime import datetime
from typing import List

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


def find_test_data(desired_version: str = '0.4') -> asf.ASFSearchResults:
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
    return results


def filter_restults_to_california_dataset(results: asf.ASFSearchResults) -> List[asf.ASFProduct]:
    """Filter the search results to only include granules from the California test dataset.

    Args:
        results: The search results to filter.

    Returns:
        A list of granules that are part of the California test dataset.
    """
    desired_results = []
    for result in results:
        scene_name = result.properties['sceneName']
        frame = int(scene_name.split('_')[4][1:])
        reference_date = datetime.strptime(scene_name.split('_')[-4], DATE_FORMAT)
        secondary_date = datetime.strptime(scene_name.split('_')[-3], DATE_FORMAT)
        creation_date = datetime.strptime(scene_name.split('_')[-1], DATE_FORMAT)

        reference_within_data_date_range = DATA_START <= reference_date <= DATA_END
        secondary_within_data_date_range = DATA_START <= secondary_date <= DATA_END
        within_data_date_range = reference_within_data_date_range and secondary_within_data_date_range
        within_processing_date_range = PROCESSING_START <= creation_date <= PROCESSING_END
        desired_frame = frame in CAL_FRAMES

        if within_data_date_range and within_processing_date_range and desired_frame:
            desired_results.append(result)
    return desired_results


def find_california_dataset() -> List[asf.ASFProduct]:
    """Find all OPERA L3 DISP S1 PROVISIONAL V0.4 granules created for California test dataset.

    Returns:
        A list of granules that are part of the California test dataset.
    """
    results = find_test_data()
    desired_results = filter_restults_to_california_dataset(results)
    return desired_results

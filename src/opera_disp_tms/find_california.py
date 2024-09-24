"""Find all OPERA L3 DISP S1 PROVISIONAL V0.4 granules created for California test dataset."""
from datetime import datetime

import asf_search as asf


# https://github.com/nasa/opera-sds/issues/54
issue_open_date = datetime.strptime('20240917T144641Z', '%Y%m%dT%H%M%SZ')
des_frames = [
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
asc_frames = [
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
    # 24728, # Not enough scenes avaialable
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
cal_frams = sorted(asc_frames + des_frames)

session = asf.ASFSession(edl_host='uat.urs.earthdata.nasa.gov')
disp_opts = asf.ASFSearchOptions(
    session=session, host='cmr.uat.earthdata.nasa.gov', shortName='OPERA_L3_DISP-S1_PROVISIONAL_V0'
)
disp_opts.maxResults = None
cmr_keywords = [('options[readable_granule_name][pattern]', 'true')]
# granule_name_wildcard = ['*_v0.4_*']
granule_name_wildcard = ['*']
results = asf.search(opts=disp_opts, cmr_keywords=cmr_keywords, granule_list=granule_name_wildcard)

frames = []
creation_dates = []
desired_results = []
versions = []
for result in results:
    scene_name = result.properties['sceneName']
    frame = int(scene_name.split('_')[4][1:])
    creation_date = datetime.strptime(scene_name.split('_')[-1], '%Y%m%dT%H%M%SZ')
    version = scene_name.split('_')[-2]
    if creation_date >= issue_open_date:
        desired_results.append(result)
        frames.append(frame)
        creation_dates.append(creation_date)
        versions.append(version)
frames = sorted(list(set(frames)))
versions = sorted(list(set(versions)))

breakpoint()
print(f'Found {len(desired_results)} results')
print('Earliest creation date:', min(creation_dates))
print('Latest creation date:', max(creation_dates))

missing_frames = list(set(cal_frams) - set(frames))
if len(missing_frames) > 0:
    print('Missing frames:', missing_frames)
else:
    print('All frames accounted for')

extra_frames = list(set(frames) - set(cal_frams))
if len(extra_frames) > 0:
    print('Extra frames:', extra_frames)

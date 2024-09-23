"""Find all OPERA L3 DISP S1 PROVISIONAL V0.4 granules created for California test dataset."""
from datetime import datetime

import asf_search as asf


session = asf.ASFSession(edl_host='uat.urs.earthdata.nasa.gov')
disp_opts = asf.ASFSearchOptions(
    session=session, host='cmr.uat.earthdata.nasa.gov', shortName='OPERA_L3_DISP-S1_PROVISIONAL_V0'
)
disp_opts.maxResults = None
cmr_keywords = [('options[readable_granule_name][pattern]', 'true')]
granule_name_wildcard = ['*_v0.4_*']
results = asf.search(opts=disp_opts, cmr_keywords=cmr_keywords, granule_list=granule_name_wildcard)

# https://github.com/nasa/opera-sds/issues/54
issue_open_date = datetime.strptime('20240917T144641Z', '%Y%m%dT%H%M%SZ')
frames = []
creation_dates = []
desired_results = []
for result in results:
    scene_name = result.properties['sceneName']
    frame = int(scene_name.split('_')[4][1:])
    creation_date = datetime.strptime(scene_name.split('_')[-1], '%Y%m%dT%H%M%SZ')
    if creation_date >= issue_open_date:
        desired_results.append(result)
        frames.append(frame)
        creation_dates.append(creation_date)

print(f'Found {len(desired_results)} results')
print('Frames:', list(set(frames)))
print('Earliest creation date:', min(creation_dates))
print('Latest creation date:', max(creation_dates))

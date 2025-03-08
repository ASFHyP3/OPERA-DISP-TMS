import requests
import subprocess
import hyp3_sdk as sdk
import boto3
import get_frame_list_from_cmr


def update_s3_prefix(job):
    s3_prefix = f's3://asf-services-web-content-prod/main/{job.name}/'

    subprocess.run(['aws', '--profile', 'edc-prod', 's3', 'rm', s3_prefix, '--recursive'], check=True)
    subprocess.run(['aws', '--profile', 'edc-prod', 's3', 'cp',
                    f'https://hyp3-opera-disp-sandbox-contentbucket-ibxz8lcpdo59.s3.us-west-2.amazonaws.com/{job.job_id}/tms/',
                    s3_prefix, '--recursive'], check=True)


ascending_frames = get_frame_list_from_cmr.get_frame_list_from_cmr('ASCENDING')
descending_frames = get_frame_list_from_cmr.get_frame_list_from_cmr('DESCENDING')

# Remove frame 21518
ascending_frames.remove(21518)

HyP3 = sdk.HyP3('https://hyp3-opera-disp-sandbox.asf.alaska.edu/')

displacement_descending = {
    'job_type': 'OPERA_DISP_TMS',
    'name': 'disp/desc',
    'job_parameters': {
        'measurement_type': 'displacement',
        'frame_ids': descending_frames,
        'start_date': '20140101',
        'end_date': '20260101'
    }
}

displacement_ascending = {
    'job_type': 'OPERA_DISP_TMS',
    'name': 'disp/asc',
    'job_parameters': {
        'measurement_type': 'displacement',
        'frame_ids': ascending_frames,
        'start_date': '20140101',
        'end_date': '20260101'
    }
}

velocity_descending = {
    'job_type': 'OPERA_DISP_TMS',
    'name': 'vel/desc',
    'job_parameters': {
        'measurement_type': 'velocity',
        'frame_ids': descending_frames,
        'start_date': '20140101',
        'end_date': '20260101'
    }
}

velocity_ascending = {
    'job_type': 'OPERA_DISP_TMS',
    'name': 'vel/asc',
    'job_parameters': {
        'measurement_type': 'velocity',
        'frame_ids': ascending_frames,
        'start_date': '20140101',
        'end_date': '20260101'
    }
}

jobs = HyP3.submit_prepared_jobs([displacement_descending, velocity_descending,
                                  displacement_ascending, velocity_ascending])
jobs = HyP3.watch(jobs, timeout=21600, interval=300)

for job in jobs:
    response = requests.get(f'https://hyp3-opera-disp-sandbox-contentbucket-ibxz8lcpdo59.s3.us-west-2.amazonaws.com/{job.job_id}/tms/openlayers.html')
    response.raise_for_status()

for job in jobs:
    update_s3_prefix(job)
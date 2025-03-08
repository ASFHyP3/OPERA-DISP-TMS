import subprocess

import requests
from get_frame_list_from_cmr import get_frames_for_direction
import hyp3_sdk as sdk


def update_s3_prefix(job):
    source = f's3://hyp3-opera-disp-sandbox-contentbucket-ibxz8lcpdo59/{job.job_id}/tms/'
    target = f's3://asf-services-web-content-prod/main/{job.name}/'

    subprocess.run(['aws', '--profile', 'edc-prod', 's3', 'rm', target, '--recursive'], check=True)
    subprocess.run(['aws', '--profile', 'edc-prod', 's3', 'cp', source, target, '--recursive'], check=True)


def build_job(name: str, measurement_type: str, frames: list[int]) -> dict:
    return {
        'job_type': 'OPERA_DISP_TMS',
        'name': name,
        'job_parameters': {
            'measurement_type': measurement_type,
            'frame_ids': frames,
            'start_date': '20140101',
            'end_date': '20260101'
        }
    }

ascending_frames = get_frames_for_direction('ASCENDING')
descending_frames = get_frames_for_direction('DESCENDING')

# Remove frame 21518
ascending_frames.remove(21518)

HyP3 = sdk.HyP3('https://hyp3-opera-disp-sandbox.asf.alaska.edu/')

prepared_jobs = [
    build_job('disp/desc', 'displacement', descending_frames),
    build_job('disp/asc', 'displacement', ascending_frames),
    build_job('vel/desc', 'velocity', descending_frames),
    build_job('vel/asc', 'velocity', ascending_frames),
]

jobs = HyP3.submit_prepared_jobs(prepared_jobs)
jobs = HyP3.watch(jobs, timeout=21600, interval=300)

for job in jobs:
    response = requests.get(f'https://hyp3-opera-disp-sandbox-contentbucket-ibxz8lcpdo59.s3.us-west-2.amazonaws.com/{job.job_id}/tms/openlayers.html')
    response.raise_for_status()

for job in jobs:
    update_s3_prefix(job)

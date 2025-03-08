import subprocess

import hyp3_sdk as sdk
import requests
from get_frame_list_from_cmr import get_frames_for_direction


def publish_mosaic(job: sdk.Job) -> None:
    source = f's3://hyp3-opera-disp-sandbox-contentbucket-ibxz8lcpdo59/{job.job_id}/tms/'
    target = f's3://asf-services-web-content-prod/main/{job.name}/'
    subprocess.run(['aws', '--profile', 'edc-prod', 's3', 'sync', source, target], check=True)


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


def main():
    ascending_frames = get_frames_for_direction('ASCENDING')
    descending_frames = get_frames_for_direction('DESCENDING')

    # frame 21518 has disjoint temporal coverage
    if 21518 in ascending_frames:
        ascending_frames.remove(21518)

    HyP3 = sdk.HyP3('https://hyp3-opera-disp-sandbox.asf.alaska.edu/')

    prepared_jobs = [
        build_job('disp/desc', 'displacement', descending_frames),
        build_job('disp/asc', 'displacement', ascending_frames),
        build_job('vel/desc', 'velocity', descending_frames),
        build_job('vel/asc', 'velocity', ascending_frames),
    ]

    jobs = HyP3.submit_prepared_jobs(prepared_jobs)
    for job in jobs:
        print(f'https://hyp3-opera-disp-sandbox.asf.alaska.edu/jobs/{job.job_id}')
    jobs = HyP3.watch(jobs, timeout=21600, interval=120)

    for job in jobs:
        response = requests.get(f'https://hyp3-opera-disp-sandbox-contentbucket-ibxz8lcpdo59.s3.us-west-2.amazonaws.com/{job.job_id}/tms/openlayers.html')
        response.raise_for_status()

    for job in jobs:
        publish_mosaic(job)


if __name__ == '__main__':
    main()

import subprocess

import hyp3_sdk as sdk
import requests
from get_frame_list_from_cmr import get_frames_for_direction


def publish_mosaic(job: sdk.Job) -> None:
    source = f's3://hyp3-edc-prod-contentbucket-1fv14ed36ifj6/{job.job_id}/tms/'
    target = f's3://asf-services-web-content-prod/main/{job.name}/'
    subprocess.run(['aws', '--profile', 'edc-prod', 's3', 'sync', source, target, '--delete'], check=True)


def build_job(name: str, frames: list[int]) -> dict:
    return {
        'job_type': 'OPERA_DISP_TMS',
        'name': name,
        'job_parameters': {
            'frame_ids': frames,
        },
    }


def main():
    ascending_frames = get_frames_for_direction('ASCENDING')
    descending_frames = get_frames_for_direction('DESCENDING')

    HyP3 = sdk.HyP3('https://hyp3-api.asf.alaska.edu/')

    prepared_jobs = [
        build_job('desc/vel', descending_frames),
        build_job('asc/vel', ascending_frames),
    ]

    jobs = HyP3.submit_prepared_jobs(prepared_jobs)
    for job in jobs:
        print(f'https://hyp3-api.asf.alaska.edu/jobs/{job.job_id}')
    jobs = HyP3.watch(jobs, timeout=21600, interval=120)

    for job in jobs:
        response = requests.get(f'https://d3gm2hf49xd6jj.cloudfront.net/{job.job_id}/tms/openlayers.html')
        response.raise_for_status()

    for job in jobs:
        publish_mosaic(job)


if __name__ == '__main__':
    main()

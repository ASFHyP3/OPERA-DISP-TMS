import requests


def get_frame_number(item):
    for attr in item['umm']['AdditionalAttributes']:
        if attr['Name'] == 'FRAME_NUMBER':
            return int(attr['Values'][0])
    raise ValueError(f'FRAME_NUMBER not found for granule {item["umm"]["GranuleUR"]}')


def get_granules(direction):
    url = 'https://cmr.earthdata.nasa.gov/search/granules.umm_json'
    params = {
        'short_name': 'OPERA_L3_DISP-S1_V1',
        'attribute[]': f'string,ASCENDING_DESCENDING,{direction}',
        'page_size': '2000',
    }
    headers: dict = {}

    granules = []
    while True:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        granules.extend(response.json()['items'])
        if 'CMR-Search-After' not in response.headers:
            break
        headers['CMR-Search-After'] = response.headers['CMR-Search-After']
    return granules


def get_frames_for_direction(direction: str) -> list:
    granules = get_granules(direction)
    frames = {get_frame_number(granule) for granule in granules}
    return sorted(list(frames))


if __name__ == '__main__':
    for direction in ['ASCENDING', 'DESCENDING']:
        frames = get_frames_for_direction(direction)
        print(f'{direction}: {frames}')

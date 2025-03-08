import requests


def get_frame_number(item):
    for attr in item['umm']['AdditionalAttributes']:
        if attr['Name'] == 'FRAME_NUMBER':
            return int(attr['Values'][0])
    raise ValueError(f'FRAME_NUMBER not found for granule {item["umm"]["GranuleUR"]}')


def get_granules(direction):
    # TODO update url when we start working with CMR production
    url = 'https://cmr.uat.earthdata.nasa.gov/search/granules.umm_json'
    params = [
        ('short_name', 'OPERA_L3_DISP-S1_V1'),
        # TODO update PRODUCT_VERSION requirement if/when we want to focus on v1.0 data in CMR UAT
        # TODO remove PRODUCT_VERSION requirement when we start working with CMR production?
        ('attribute[]', 'float,PRODUCT_VERSION,0.9,'),
        ('attribute[]', f'string,ASCENDING_DESCENDING,{direction}'),
        ('page_size', 2000),
    ]
    # TODO update to include bearer auth when we start working with the hidden collection in CMR production
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
    # TODO remove frames that won't be successfully processed, e.g. 21518 with disjoint temporal coverage in CMR UAT
    return sorted(list(frames))


if __name__ == '__main__':
    for direction in ['ASCENDING', 'DESCENDING']:
        frames = get_frames_for_direction(direction)
        print(f'{direction}: {frames}')

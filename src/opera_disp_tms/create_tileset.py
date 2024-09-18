import json
import os
from pathlib import Path

from mapbox_tilesets.scripts.cli import upload_raster_source  # create, publish


MAPBOX_ACCOUNT = os.environ['MAPBOX_ACCOUNT']
MAPBOX_ACCESS_TOKEN = os.environ['MAPBOX_ACCOUNT']


def upload_tileset(username, id, wildcard='summer_vv_COH12'):
    files = [str(x) for x in Path.cwd().glob(f'{wildcard}*.tif')][:0]
    ctx = dict()
    upload_raster_source(ctx, username, id, files)


def create_template(
    mapbox_account, tileset_name, minzoom=2, maxzoom=6, offset=0, scale=1, units='meters', outname='template.json'
):
    template = {
        'version': 1,
        'type': 'rasterarray',
        'sources': [{'uri': f'mapbox://tileset-source/{mapbox_account}/{tileset_name}'}],
        'minzoom': minzoom,
        'maxzoom': maxzoom,
        'layers': {
            '12-Day Summber Coherence': {
                'tilesize': 512,
                'offset': offset,
                'scale': scale,
                'resampling': 'bilinear',
                'buffer': 1,
                'units': units,
            },
        },
    }
    with open(outname, 'w') as f:
        f.write(json.dumps(template, indent=2))


### Tileset CLI commands:
# tilesets upload-raster-source ffwilliams2 summer-vv-coh12-source ./summer_vv_COH12_1.tif
# tilesets create ffwilliams2.summer-vv-coh12 --recipe ./summer-vv-coh12.json --name "Coherence 12-Day Summer"
# tilesets publish ffwilliams2.summer-vv-coh12

if __name__ == '__main__':
    mapbox_source_name = 'summer-vv-coh12'
    recipe_location = './summer-vv-coh12.json'
    source_name = 'summer-vv-coh12-source'
    create_template(mapbox_account=MAPBOX_ACCOUNT, tileset_name=source_name, outname=recipe_location, maxzoom=12)

set -x

ls *.tif | xargs create_tile_map tiles/
# aws s3 cp tiles/ s3://BURCKET/YOUR/PREFIX --recursive

# OPERA-DISP-TMS

Package for [OPERA DISP](https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/) Tile Map Server (TMS) creation.

## Installation
1. Ensure that conda is installed on your system (we recommend using [mambaforge](https://github.com/conda-forge/miniforge#mambaforge) to reduce setup times).
2. Download a local version of the `OPERA-DISP-TMS` repository (`git clone https://github.com/ASFHyP3/opera-disp-tms.git`)
3. In the base directory for this project call `mamba env create -f environment.yml` to create your Python environment, then activate it (`mamba activate opera-disp-tms`)
4. Finally, install a development version of the package (`python -m pip install -e .`)

To run all commands in sequence use:
```bash
git clone https://github.com/ASFHyP3/opera-disp-tms.git 
cd OPERA-DISP-TMS
mamba env create -f environment.yml
mamba activate opera-disp-tms
python -m pip install -e .
```

## Credentials
### Earthdata
This repository assumes that you have credentials for `urs.earthdata.nasa.gov` (Earthdata login) and `uat.urs.earthdata.nasa.gov` (Earthdata login UAT) configured in your `netrc` file.

For instructions on setting up your Earthdata login (and Earthdata login UAT) via a `.netrc` file, check out this [guide](https://harmony.earthdata.nasa.gov/docs#getting-started).

### Temporary AWS credentials
The `get_tmp_s3_creds` CLI command can be used to generate temporary S3 access credentials for a NASA Cumulus Thin Egress App (TEA):
```bash
get_tmp_s3_creds --endpoint https://cumulus-test.asf.alaska.edu/s3credentials
```
Where `--endpoint` is the TEA S3 endpoint you want to generate credentials for. When called with no arguments (`get_tmp_s3_creds`) the CLI commands defaults to the ASF Cumulus UAT's TEA endpoint.

This CLI command will print three bash `export` commands to the terminal. Run these commands to configure your new temporary AWS credentials

**These temporary credentials expire every hour and will need to be regenerated accordingly.**

## Usage
> [!WARNING]
> Products in ASF's Cumulus UAT environment are not publicly accessible. To run this workflow using data hosted in ASF's Cumulus UAT environment you first need to generate temporary S3 access credentials while on the NASA or ASF DAAC VPN, then `export` the created credentials to an AWS us-west-2 compute environment. See [Temporary AWS Credentials](#temporary-aws-credentials) for more details.

### Create a frame metadata tile
These tiles serve as the foundation for the creation of all other Tile Map Server datasets. More details on the structure of these datasets can be found in the [Design.md](https://github.com/ASFHyP3/OPERA-DISP-TMS/blob/develop/Design.md) document.

The `generate_metadata_tile` CLI command can be used to generate a frame metadata tile:
```bash
metadata_frame_tile -125 42 ascending
```
Where `-125 42` is the upper-left corner of the desired bounding box in **integer** `minx maxy` longitude/latitude values, and `ascending` specifies which orbit direction you want to generate a frame metadata tile for (`ascending` or `descending`).

For TMS generation ASF will be using 1x1 degree tiles.

The resulting products have the name format:
`METADATA_{orbit direction}_{upper left corner in lon/lat}.tif`.
For example:
`METADATA_ASCENDING_W125N42.tif`

### Create a Short Wavelength Cumulative Displacement tile
The `generate_sw_disp_tile` CLI command can be used to generate a cumulative displacement geotiff:
```bash
generate_sw_disp_tile METADATA_ASCENDING_W125N42.tif 20170901 20171231
```
Where `METADATA_ASCENDING_W125N42.tif` is the path to the frame metadata tile you want to generate a Short Wavelength Cumulative Displacement tile for, and `20170901`/`20171231` specify the start/end of the secondary date search range to generate a tile for in format `%Y%m%d`.

The resulting products have the name format:
`SW_CUMUL_DISP_{start date search range}_{stop data search range}_{orbit direction}_{upper left corner in lon/lat}.tif`
For example:
`SW_CUMUL_DISP_20170901_20171231_ASCENDING_W125N42.tif`

### Create a Tile Map
The `create_tile_map` CLI command generates a directory with small .png tiles from a list of rasters in a common projection, following the OSGeo Tile Map Service Specification, using gdal2tiles: https://gdal.org/en/latest/programs/gdal2tiles.html

To create a tile map from a set of displacement GeoTIFFs:
```bash
create_tile_map tiles/ \
  SW_CUMUL_DISP_20170901_20171231_ASCENDING_W125N42.tif \
  SW_CUMUL_DISP_20170901_20171231_ASCENDING_W125N42.tif \
  SW_CUMUL_DISP_20170901_20171231_ASCENDING_W125N42.tif
```

A simple web page with a viewer based on OpenLayers is included to visualize the map in a browser, e.g. `tiles/openlayers.html`.

The output directory can be copied to a public AWS S3 bucket (or any other web server) to access the map tiles over the internet:
```
aws s3 cp tiles/ s3://myBucket/tiles/ --recursive
```
The online map can then be reviewed in a browser, e.g. https://myBucket.s3.amazonaws.com/tiles/openlayers.html

## License
The OPERA-DISP-TMS package is licensed under the Apache License, Version 2 license. See the LICENSE file for more details.

## Code of conduct
We strive to create a welcoming and inclusive community for all contributors. As such, all contributors to this project are expected to adhere to our code of conduct.

Please see `CODE_OF_CONDUCT.md` for the full code of conduct text.

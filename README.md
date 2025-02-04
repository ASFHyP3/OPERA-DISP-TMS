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

This application requires Earthdata Login UAT credentials to download OPERA Displacement data. These credentials can be provided either via a `uat.urs.earthdata.nasa.gov` entry in your `.netrc` file, or via `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` environment variables.

For instructions on setting up your Earthdata Login via a `.netrc` file, check out this [guide](https://harmony.earthdata.nasa.gov/docs#getting-started).

> [!WARNING]
> This application uses [S3 Direct Access](https://cumulus-test.asf.alaska.edu/s3credentialsREADME) to download OPERA Displacement data, and must be run in the `us-west-2` AWS region.

## Usage

### Create a Short Wavelength Cumulative Displacement GeoTIFF
The `create_measurement_geotiff` CLI command can be used to generate a cumulative displacement geotiff for a given OPERA frame:
```bash
create_measurement_geotiff 11115 displacement 20140101 20260101
```
Where `11115` is OPERA frame id of the granule stack in CMR, and `20170901`/`20171231` specify the start/end of the secondary date search range in format `%Y%m%d`.

The resulting products have the name format:
`displacement_{frame id}_{start date}_{end_date}.tif`
For example:
`displacement_11115_20140101_20260101.tif`

### Create a Short Wavelength Velocity GeoTIFF
The `create_measurement_geotiff` CLI command can be used to generate a short wavelength velocity geotiff for a given OPERA frame:
```bash
create_measurement_geotiff 11115 velocity 20140101 20260101
```
Where `11115` is OPERA frame id of the granule stack in CMR, and `20170901`/`20171231` specify the start/end of the secondary date search range in format `%Y%m%d`.

The velocity will be calculated from the minimum set of granules needed to span the temporal search range.

The resulting products have the name format:
`velocity_{frame id}_{start date}_{end_date}.tif`
For example:
`velocity_11115_20140101_20260101.tif`

### Create a Tile Map
The `create_tile_map` CLI command generates a directory with small.png tiles from a s3 bucket with a list of rasters in a common projection, following the OSGeo Tile Map Service Specification, using gdal2tiles: https://gdal.org/en/latest/programs/gdal2tiles.html

To create a tile map from a set of displacement GeoTIFFs:
```bash
create_tile_map tiles displacement --bucket myBucket --bucket-prefix myPrefix
```

This will look for all `.tif` files in `myBucket/myPrefix/` and use them to make the tile map.

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

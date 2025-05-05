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

This application requires Earthdata Login credentials to download OPERA Displacement data. These credentials can be provided either via a `urs.earthdata.nasa.gov` entry in your `.netrc` file, or via `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` environment variables.

For instructions on setting up your Earthdata Login via a `.netrc` file, check out this [guide](https://harmony.earthdata.nasa.gov/docs#getting-started).

## Usage

### Deliver updated velocity mosaics to the ASF Displacement Portal

The `weekly-tileset-generation.py` script delivers updated velocity mosaics to the ASF Displacement portal at https://displacement.asf.alaska.edu. This script:
1. Queries CMR for `OPERA_L3_DISP-S1_V1` granules to determine the ascending and descending frames for which data is available.
1. Submits `OPERA_DISP_TMS` jobs to https://hyp3-api.asf.alaska.edu/ to generate ascending and descending mosaics.
1. Syncs the new mosaics to the production hosting bucket at `s3://asf-services-web-content-prod/`.

To run this script:
1. Configure an `edc-prod` profile in your `.aws/config` and `.aws/credentials` files.
   1. (Optional) For speedier results, run from `us-west-2` and increase `max_concurrent_requests` per [AWS CLI S3 Configuration](https://docs.aws.amazon.com/cli/latest/topic/s3-config.html).
1. Set up your .netrc file per [Credentials](#credentials).
1. Install the application per [Installation](#installation) and activate the conda environment.
1. Navigate to the scripts directory and run the script.
   1. (Optional) This script will take hours to run, so running it as a background process via `screen` or `tmux` is recommended.
   1. `cd scripts; python weekly-tileset-generation.py`

### Create a Short Wavelength Velocity GeoTIFF

> [!WARNING]
> This application uses [S3 Direct Access](https://cumulus.asf.alaska.edu/s3credentialsREADME) to download OPERA Displacement data, and must be run in the `us-west-2` AWS region.

The `create_measurement_geotiff` CLI command can be used to generate a short wavelength velocity geotiff for a given OPERA frame:
```bash
create_measurement_geotiff 11115 velocity 20140101 20260101
```
Where `11115` is OPERA frame id of the granule stack in CMR, and `20140101`/`20260101` specify the start/end of the secondary date search range in format `%Y%m%d`.

The velocity will be calculated from the minimum set of granules needed to span the temporal search range.

The resulting products have the name format:
`velocity_{frame id}_{start date}_{end_date}.tif`
For example:
`velocity_11115_20140101_20260101.tif`

### Create a Tile Map
The `create_tile_map` CLI command generates a directory with small.png tiles from a s3 bucket with a list of rasters in a common projection, following the OSGeo Tile Map Service Specification, using gdal2tiles: https://gdal.org/en/latest/programs/gdal2tiles.html

To create a tile map from a set of velocity GeoTIFFs:
```bash
create_tile_map velocity --bucket myBucket --bucket-prefix myPrefix
```

This will look for all `.tif` files in `s3://myBucket/myPrefix/` and use them to make the tile map.

A simple web page with a viewer based on OpenLayers is included to visualize the map in a browser, e.g. `tiles/openlayers.html`.

The output directory can be copied to a public AWS S3 bucket (or any other web server) to access the map tiles over the internet:
```
aws s3 cp tiles/ s3://myBucket/tiles/ --recursive
```
The online map can then be reviewed in a browser, e.g. https://myBucket.s3.amazonaws.com/tiles/openlayers.html

## Mosaic Strategy

The general strategy used to produce the mosaic visualizations is as follows:

1. For each of ASCENDING and DESCENDING:
   1. Query CMR to identify all frames with data for the given flight direction
   1. For each frame, create an average velocity GeoTIFF
      1. Find the minimum set of granules spanning the full temporal extent of the available data
      1. Create a short wavelength displacement time series from those granules
      1. Take a linear regression of that time series to determine velocity
         1. If a pixel is NoData in <= 10% of granules, treat NoData as zero in the time series for that pixel
         1. If a pixel is NoData in > 10% of granules, set the velocity for that pixel to NoData
      1. Set values outside [-0.03 m/yr, +0.03 m/yr] to -0.03 and +0.03
      1. Write the average velocity values to a geotiff
   1. Overlay the individual frame GeoTIFFs into a mosaic
      1. In areas where multiple frames overlap, prefer showing near-range pixels over far-range pixels (e.g. easternmost frame on top for ascending, westernmost on top for descending)
      1. If the preferred frame has no data for a particular pixel, let the data value of the less-preferred frame show through

## License
The OPERA-DISP-TMS package is licensed under the Apache License, Version 2 license. See the LICENSE file for more details.

## Code of conduct
We strive to create a welcoming and inclusive community for all contributors. As such, all contributors to this project are expected to adhere to our code of conduct.

Please see `CODE_OF_CONDUCT.md` for the full code of conduct text.

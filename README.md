# OPERA-DISP-TMS

Package for [OPERA DISP](https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/) Tile Map Server (TMS) creation.

## Installation
See [Develop Setup](#developer-setup)

## Credentials
### Earthdata
This repository assumes that you have credentials for `urs.earthdata.nasa.gov` (Earthdata login) and `uat.urs.earthdata.nasa.gov` (Earthdata login UAT) configured in your `netrc` file.

For instructions on setting up your Earthdata login (and Earthdata login UAT) via a `.netrc` file, check out this [guide](https://harmony.earthdata.nasa.gov/docs#getting-started).

### Temporary S3 credentials
The `get_tmp_s3_creds` CLI command can be used to generate temporary S3 access credentials for a NASA Cumulus Thin Egress App (TEA):
```bash
get_tmp_s3_creds --tea-url https://cumulus-test.asf.alaska.edu/s3credentials --creds-path ~/LOCAL_OPERA-DISP-TMS_INSTALL_PATH/src/opera_disp_tms/credentials.json
```
Where `--tea-url` is the TEA S3 endpoint you want to generate credentials for, and `--creds-path` is the path to save the credentials to.
When called with no arguments (`get_tmp_s3_creds`) the CLI commands defaults to the ASF Cumulus UAT's TEA, and to the credentials path `~/LOCAL_OPERA-DISP-TMS_INSTALL_PATH/src/opera_disp_tms/credentials.json`. Tools within this package expect the credentials to be stored at `~/LOCAL_OPERA-DISP-TMS_INSTALL_PATH/src/opera_disp_tms/credentials.json`, so if you're manually generating your credentials make sure to save them in this location.

**These temporary credentials expire every hour and will need to be regenerated accordingly.**

## Usage
### Create a frame metadata tile
These tiles serve as the foundation for the creation of all other Tile Map Server datasets. More details on the structure of these datasets can be found in the [Design.md](https://github.com/ASFHyP3/OPERA-DISP-TMS/blob/develop/Design.md) document.

> [!WARNING]
> Products in ASF's Cumulus UAT environment are not publicly accessible. To run this workflow using data hosted in ASF's Cumulus UAT environment you first need to generate temporary S3 access credentials while on the NASA or ASF DAAC VPN, then copy the created credentials to an AWS us-west-2 compute environment at the location `~/LOCAL_OPERA-DISP-TMS_INSTALL_PATH/src/opera_disp_tms/credentials.json`. See [Create temp S3 credentials](#temporary-s3-credentials) for more details.

The `generate_frame_tile` CLI command can be used to generate a frame metadata tile:
```bash
generate_frame_tile -122 37 -121 38 --ascending
```
Where `-122 37 -121 38` is a desired bounding box in **integer** `minx, miny, max, maxy` longitude/latitude values, and `--ascending` specifies which orbit direction you want to generate a frame metadata tile for (`--ascending` for ascending, omit for descending).

For TMS generation ASF will be using 1x1 degree tiles.

## Developer Setup
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
## License
The OPERA-DISP-TMS package is licensed under the Apache License, Version 2 license. See the LICENSE file for more details.

## Code of conduct
We strive to create a welcoming and inclusive community for all contributors. As such, all contributors to this project are expected to adhere to our code of conduct.

Please see `CODE_OF_CONDUCT.md` for the full code of conduct text.

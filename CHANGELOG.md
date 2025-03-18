# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [PEP 440](https://www.python.org/dev/peps/pep-0440/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.4]

### Changed
* Mosaics are now generated from `OPERA_L3_DISP-S1_V1` data in ASF's production archive, rather than the UAT archive.
* The `weekly-tileset-generation.py` script now submits jobs to hyp3-api, rather than hyp3-opera-disp-sandbox.
* `weekly-tileset-generation.py` no longer produces displacement mosaics, only velocity mosaics.

## [0.8.3]

### Added
* Utility scripts `get_frame_list_from_cmr.py` to list all frames for which data exists in CMR and `weekly-tileset-generation` to update OPERA tilesets with up-to-date data

## [0.8.2]

### Changed
* `create_tile_map` now uses median resampling instead of nearest neighbor resampling when building the TMS mosaic.
  Significantly fewer NoData pixels are shown when zoomed out; NoData pixels gradually appear when zooming in.

## [0.8.1]

### Changed
* `prep_stack.find_needed_granules` now filters duplicate granules for the same frame id/reference date/secondary date, keeping the granule with the most recent creation date.

## [0.8.0]

### Changed
* Map scale range is now globally [-0.05, 0.05] for velocity/secant_velocity and [-0.25, 0.25] for displacement.

### Fixed
* Values beyond bounds of measurement are now correctly clipped to the min/max value instead of set to NaN.
* Units are now m/yr for velocity/secant_velocity and m for displacement.

## [0.7.0]
Strategy to create the Tile Map Service has been updated to create measurement geotiffs for each OPERA frame, rather
than creating measurement geotiffs for each 1x1 degree tile.

### Changed
* The container now accepts `++process` which can be `create_measurement_geotiff` or `create_tile_map`.
* `create_measurement_geotiff` replaces both `generate_sw_disp_tile` and `generate_sw_vel_tile`. This script takes a
  frame id, measurement type, start date, and end date, computes the requested measurement value (displacement,
  secant_velocity, velocity) for the given frame and date range, and outputs a geotiff in EPSG:3857.
* `create_measurement_geotiff` and `create_tile_map` now take `--bucket` and `--bucket-prefix` as params and uploads results to bucket
* `create_tile_map` downloads all tifs from `--bucket` and `--bucket-prefix` params as inputs
* Changed frame ordering strategy so that near range paths are displayed over far range paths.

### Removed
* `generate_metadata_tile.py` has been removed, as creation of metadata tiles is no longer necessary
* `frames.py` has been removed. The user is now expected to provide the list of OPERA frames for which to create a
  visualization. All necessary data and metadata are available in CMR, so we no longer depend on the OPERA frame
  database.
* The `scripts/` directory has been removed. These helper scripts provided commands for generating a visualization of
  the California data set delivered by the project for initial testing. This application can now act on arbitrary v0.9+
  data in CMR UAT, so the California-specific scripts are no longer necessary.
* Outdated `Design.md` describing the previous tile-by-tile strategy has been removed.

## [0.6.0]
### Added
* Add scale range value and units to extent.json output file

## [0.5.1]
### Added
* Add `mypy` to [`static-analysis`](.github/workflows/static-analysis.yml).

## [0.5.0]
### Added
* Granule orbit directions are now taken from the ASCENDING_DESCENDING attribute in CMR, rather than the frame database
* Support for generating velocity mosaics from granule stacks without a common reference date

### Changed
* Revised `search.py` to query all v0.9+ granules in CMR UAT, rather than California-specific v0.7 granules
* Accommodate `FRAME_ID` CMR attribute being renamed to `FRAME_NUMBER`
* HyP3 entrypoint now generates mosaic GeoTIFFs in 10 degree x 10 degree partitions to limit memory usage

## [0.4.1]
### Changed
* The [`static-analysis`](.github/workflows/static-analysis.yml) Github Actions workflow now uses `ruff` rather than `flake8` for linting.

## [0.4.0]
### Added
* Ability to update the reference date for OPERA DISP granule xarray objects
* Integration with CMR metadata when searching for granules
* Entrypoint and docker container generation capability for HyP3
* The docker container is built and pushed to the Github Container Registry via Github Actions

### Changed
* find_california_dataset.py to search.py and added functionality to search for granules in CMR
* Updated all scripts to use the new find_california_granules_for_frame function
* `generate_sw_disp_tile.py` now masks using `recomended_mask`
* Authentication now requires Earthdata Login UAT credentials provided via .netrc or environment variables

### Removed
* CSV-based caching of granules in favor of CMR-based searching
* Command line interface and entrypoint for get_tmp_s3_creds.py

### Fixed
* s3fs/xarray resources are now closed when no longer used, resolving an issue where attempting to open new resources could hang indefinitely

## [0.3.0]
### Added
* Ability to generate SW velocity tiles in `generated_sw_vel_tile.py`

### Changed
* California dataset scripts to allow for generation of SW velocity tiles
* Rename `generate_frame_tile.py` to `generate_metadata_tile.py`
* Simplified CLI and filenames of metadata tiles so that location is specified by the upper-left corner of the tile, not the full bounding box
* Expanded/modified some functions in `generate_sw_disp_tile.py` so that they could be reused by `generate_sw_vel_tile.py`

### Fixed
* `extent.json` will be written during `create_tile_map.py` even if the directory `tiles/` does not exist prior to running

## [0.2.0]
### Added
* Python scripts for generating California SW Disp tileset

### Changed
* metadata tile script name from `generate_frame_tile.py` to `generate_metadata_tile.py`
* `generate_frame_tile.py` CLI to take upper left corner of bounding box, instead of full bounding box, as input
* Frame ordering strategy so that west most relative orbits are on top for ascending data, and on the bottom for descending data

### Fixed
* Removal of empty metadata tile is now conditional on the tile being all nodata, not the absence of granules

## [0.1.2]
### Added
* Bounds of the mosaic created in `create_tile_map.py` are written to a json file in tile folder
### Changed
* When generating SW_CUMUL_DISP tiles, set areas where unwrapping failed (connected components = 0) to nodata.

## [0.1.1]
### Changed
* Calculate true minimum/maximum data values in `create_tile_map` to avoid extreme displacement values being set to
  NoData. Fixes [#8](https://github.com/ASFHyP3/OPERA-DISP-TMS/issues/8).

## [0.1.0]
### Added
* Utility for creating a test dataset using [Global Coherence Dataset](https://registry.opendata.aws/ebd-sentinel-1-global-coherence-backscatter/)
* Design document with implementation details for tile generation
* Utility for identifying California test dataset
* Utility for generating metadata tile images
* Utility for generating temporary S3 credentials for [NASA Thin Egress Apps](https://nasa.github.io/cumulus/docs/deployment/thin_egress_app/)
* Utility for generating short wavelength displacement tiles
* Utility for creating a .png Tile Map from a list of displacement GeoTIFFs

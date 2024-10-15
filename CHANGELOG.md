# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [PEP 440](https://www.python.org/dev/peps/pep-0440/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3]
### Added
* Bash scripts for generating California SW Disp tileset

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

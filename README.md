# OPERA-DISP-TMS

Package for [OPERA DISP](https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/) Tile Map Server (TMS) creation.

## Scripts
`generate_coh_tiles.py`: Generate a test dataset with a similar extent and result to the OPERA DISP dataset for testing.

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

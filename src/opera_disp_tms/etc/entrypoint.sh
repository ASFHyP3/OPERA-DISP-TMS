#!/bin/bash --login
set -e
conda activate opera-disp-tms
exec python -um opera_disp_tms "$@"
from datetime import datetime

import numpy as np
import xarray as xr

from opera_disp_tms.s3_xarray import open_opera_disp_granule, s3_xarray_dataset
from opera_disp_tms.search import Granule, eliminate_duplicates, find_granules_for_frame
from opera_disp_tms.utils import within_one_day


def restrict_to_spanning_set(granules: list[Granule]) -> list[Granule]:
    """Restrict a list of granules to the minimum set needed to reconstruct the relative displacement

    Args:
        granules: List of granules to restrict

    Returns:
        List of granules that form the minimum set needed to reconstruct the relative displacement
    """
    assert len(set(g.frame_id for g in granules)) == 1, 'Spanning set granules must be from the same frame.'
    granules = sorted(granules, key=lambda x: x.secondary_date)
    first_reference_date = granules[0].reference_date
    reference_date = granules[-1].reference_date
    spanning_granules = [granules[-1]]
    while not within_one_day(reference_date, first_reference_date):
        possible_connections = [g for g in granules if within_one_day(g.secondary_date, reference_date)]
        if len(possible_connections) == 0:
            raise ValueError('Granules do not form a spanning set.')
        # This could be improved by exploring every branch of the tree, instead of just the longest branch
        next_granule = min(possible_connections, key=lambda x: x.reference_date)
        spanning_granules.append(next_granule)
        reference_date = next_granule.reference_date
    spanning_granules = sorted(spanning_granules, key=lambda x: x.secondary_date)
    return spanning_granules


def find_needed_granules(frame_id: int, begin_date: datetime, end_date: datetime, strategy: str) -> list[Granule]:
    """Find the granules needed to generate a short wavelength displacement tile.

    Args:
        frame_id: The frame id to generate the tile for
        begin_date: Start of secondary date search range to generate tile for
        end_date: End of secondary date search range to generate tile for
        strategy: Selection strategy for granules within search date range ("max", "minmax" or "all")
                  - Use "spanning" to get the minimum set of granules needed to reconstruct the relative displacement
                  - Use "all" to get all granules
    Returns:
        List of granules.
    """
    granules_full_stack = find_granules_for_frame(frame_id)
    granules = [g for g in granules_full_stack if begin_date <= g.secondary_date <= end_date]
    granules = eliminate_duplicates(granules)
    if strategy == 'spanning':
        needed_granules = restrict_to_spanning_set(granules)
    elif strategy == 'all':
        needed_granules = granules
    else:
        raise ValueError(f'Invalid strategy: {strategy}. Must be "spanning" or "all".')
    needed_granules = sorted(needed_granules, key=lambda x: x.secondary_date)
    print(f'Found {len(needed_granules)} granules for frame {frame_id} between {begin_date} and {end_date}')
    return needed_granules


def load_sw_disp_granule(granule: Granule) -> xr.DataArray:
    """Load the short wavelength displacement data for and OPERA DISP granule.
    Clips to frame map and masks out invalid data.

    Args:
        granule: The granule to load

    Returns:
        The short wavelength displacement data as an xarray DataArray
    """
    datasets = ['short_wavelength_displacement', 'recommended_mask']
    with s3_xarray_dataset(granule.s3_uri) as ds:
        granule_xr = open_opera_disp_granule(ds, granule.s3_uri, datasets)
        granule_xr = granule_xr.load()
        valid_data_mask = granule_xr['recommended_mask'] == 1
        sw_cumul_disp_xr = granule_xr['short_wavelength_displacement'].where(valid_data_mask, np.nan)
        sw_cumul_disp_xr.attrs = granule_xr.attrs
    return sw_cumul_disp_xr


def check_connected_network(granule_xrs: list[xr.DataArray]) -> None:
    """Check that cumulative displacement can reconstructed using given granule set.

    Args:
        granules_xr: A list of granule xarray DataArrays
    """
    reference_dates = sorted(list({g.reference_date for g in granule_xrs}))
    secondary_dates = sorted(list({g.secondary_date for g in granule_xrs}))
    for reference_date in reference_dates[1:]:
        if not any([within_one_day(reference_date, s) for s in secondary_dates]):
            raise ValueError('Granule network is unconnected')


def align_to_common_reference_date(granule_xrs: list[xr.DataArray], start_date: datetime) -> None:
    """Align granules to a common reference date, correcting reference date changes.

    Args:
        granule_xrs: A list of granule xarray DataArrays
        start_date: The start date to align to
    """
    granule_xrs.sort(key=lambda x: x.secondary_date)
    check_connected_network(granule_xrs)

    if start_date <= granule_xrs[0].reference_date:
        zero_xr = granule_xrs[0].copy()
        zero_xr.attrs['secondary_date'] = zero_xr.attrs['reference_date']
        zero_xr.data = np.zeros(zero_xr.shape)
        granule_xrs.insert(0, zero_xr)

    previous_granule_xr = granule_xrs[0]
    correction = -previous_granule_xr.data

    for granule_xr in granule_xrs:
        if not within_one_day(granule_xr.reference_date, previous_granule_xr.reference_date):
            correction = previous_granule_xr.data
        granule_xr += correction
        previous_granule_xr = granule_xr

    for granule_xr in granule_xrs:
        granule_xr.attrs['reference_date'] = granule_xrs[0].secondary_date


def load_sw_disp_stack(frame_id: int, begin_date: datetime, end_date: datetime, strategy: str):
    """Load the short wavelength displacement data for a frame and date range.
    Update the reference date of all granules to the earliest reference date.

    Args:
        frame_id: The frame id to load
        begin_date: The start of the date range
        end_date: The end of the date range
        strategy: The strategy to use for selecting granules ("spanning" or "all")
    """
    granules = find_needed_granules(frame_id, begin_date, end_date, strategy)
    granule_xrs = [load_sw_disp_granule(x) for x in granules]
    align_to_common_reference_date(granule_xrs, min(g.reference_date for g in granule_xrs))
    return granule_xrs

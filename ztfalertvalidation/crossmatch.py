"""
Scripts for mapping the sources of the two pipelines onto each other
"""

import logging
from pathlib import Path

import pandas as pd
from astropy.coordinates import SkyCoord
from tqdm import tqdm

from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)

GROUP_COLUMNS = ["jd", "rcid"]


def add_nearest(
    left: pd.DataFrame, right: pd.DataFrame, name_column: str, dist_column: str
) -> pd.DataFrame:
    """
    Add the nearest source of one table to each row of another

    Only sources of the same exposure quadrant are matched, since the two
    pipelines give the same source different names and ids. Every row gets its
    nearest match, however far away it is, so the distance is what decides
    whether the two are the same source. A row whose quadrant is missing from
    the other table gets no match.

    :param left: Table to add the columns to
    :param right: Table to find the nearest source in
    :param name_column: Name of the column of matched source names
    :param dist_column: Name of the column of separations, in arcseconds
    :return: Copy of the left table, with the two columns added
    """
    left_coords = SkyCoord(left["ra"].to_numpy(), left["dec"].to_numpy(), unit="deg")
    right_coords = SkyCoord(right["ra"].to_numpy(), right["dec"].to_numpy(), unit="deg")

    right_names = right["objectId"].to_numpy()
    names = pd.Series(pd.NA, index=left.index, dtype="object")
    dists = pd.Series(float("nan"), index=left.index, dtype="float64")

    right_groups = right.groupby(GROUP_COLUMNS).indices
    left_groups = left.groupby(GROUP_COLUMNS).indices

    for group, rows in tqdm(left_groups.items(), unit="quadrant"):
        matches = right_groups.get(group)
        if matches is None:
            continue

        index, separation, _ = left_coords[rows].match_to_catalog_sky(
            right_coords[matches]
        )
        names.iloc[rows] = right_names[matches][index]
        dists.iloc[rows] = separation.arcsec

    logger.info(f"Matched {names.notna().sum()} of {len(left)} alerts")

    return left.assign(**{name_column: names, dist_column: dists})


def get_matched_ipac_table(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load the IPAC alerts of a night, with the nearest DZA source of each

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per IPAC alert
    """
    return add_nearest(
        get_ipac_table(night, data_dir),
        get_dza_table(night, data_dir),
        "DZAname",
        "DZAdist",
    )


def get_matched_dza_table(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load the DZA alerts of a night, with the nearest IPAC source of each

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per DZA alert
    """
    return add_nearest(
        get_dza_table(night, data_dir),
        get_ipac_table(night, data_dir),
        "IPACname",
        "IPACdist",
    )

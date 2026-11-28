"""
Scripts for mapping the sources of the two pipelines onto each other
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
from tqdm import tqdm

from ztfalertvalidation.paths import get_night_dir
from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)

GROUP_COLUMNS = ["jd", "rcid"]
MAX_SEPARATION_ARCSEC = 1.0
IPAC_MATCH_FILE = "matches_ipac.parquet"
DZA_MATCH_FILE = "matches_dza.parquet"


def nearest_per_quadrant(
    left: pd.DataFrame, right: pd.DataFrame
) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Find the nearest source of one table for each row of another

    Only sources of the same exposure quadrant are matched, since the two
    pipelines give the same source different names and ids.

    :param left: Table to match
    :param right: Table to find the nearest source in
    :return: Per quadrant, the rows of the left table matched within
        MAX_SEPARATION_ARCSEC, the rows of the right table they matched, and
        the separations
    """
    left_coords = SkyCoord(left["ra"].to_numpy(), left["dec"].to_numpy(), unit="deg")
    right_coords = SkyCoord(right["ra"].to_numpy(), right["dec"].to_numpy(), unit="deg")

    right_groups = right.groupby(GROUP_COLUMNS).indices

    for group, rows in tqdm(
        left.groupby(GROUP_COLUMNS).indices.items(), unit="quadrant"
    ):
        matches = right_groups.get(group)
        if matches is None:
            continue

        index, separation, _ = left_coords[rows].match_to_catalog_sky(
            right_coords[matches]
        )

        close = separation.arcsec < MAX_SEPARATION_ARCSEC
        yield rows[close], matches[index][close], separation.arcsec[close]


def match_tables(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    """
    Match each alert of one table to the nearest alert of another

    The pairs are given by candid, which is unique to one alert, so a pair
    survives the tables being built again.

    :param left: Table to match
    :param right: Table to find the nearest alert in
    :return: Table of one row per matched pair
    """
    matched = list(nearest_per_quadrant(left, right))
    empty = np.array([], dtype=int)

    rows = np.concatenate([x[0] for x in matched]) if matched else empty
    matches = np.concatenate([x[1] for x in matched]) if matched else empty
    separations = np.concatenate([x[2] for x in matched]) if matched else empty

    return pd.DataFrame(
        {
            "candid": left["candid"].to_numpy()[rows],
            "match_candid": right["candid"].to_numpy()[matches],
            "separation": separations,
        }
    )


def load_cached_matches(
    left: pd.DataFrame, right: pd.DataFrame, path: Path
) -> pd.DataFrame:
    """
    Match two tables, matching them only once

    Matching a night takes several seconds and the report needs it more than
    once, so the pairs are written to parquet and read back from there. Delete
    the parquet file to match again.

    :param left: Table to match
    :param right: Table to find the nearest alert in
    :param path: Parquet file caching the pairs
    :return: Table of one row per matched pair
    """
    if path.exists():
        logger.info(f"Reading cached matches from {path}")
        return pd.read_parquet(path)

    matches = match_tables(left, right)

    logger.info(f"Caching {len(matches)} matches to {path}")
    matches.to_parquet(path)

    return matches


def get_ipac_matches(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Get the DZA alert nearest to each IPAC alert of a night

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per matched pair
    """
    return load_cached_matches(
        get_ipac_table(night, data_dir),
        get_dza_table(night, data_dir),
        get_night_dir(night, data_dir) / IPAC_MATCH_FILE,
    )


def get_dza_matches(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Get the IPAC alert nearest to each DZA alert of a night

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per matched pair
    """
    return load_cached_matches(
        get_dza_table(night, data_dir),
        get_ipac_table(night, data_dir),
        get_night_dir(night, data_dir) / DZA_MATCH_FILE,
    )


def add_matches(
    left: pd.DataFrame, right: pd.DataFrame, matches: pd.DataFrame, prefix: str
) -> pd.DataFrame:
    """
    Add the name, candid and separation of each alert's matched source

    The candid is kept as a nullable integer: an unmatched alert would
    otherwise make the column a float, and a candid does not survive being
    one.

    :param left: Table to add the columns to
    :param right: Table the alerts were matched in
    :param matches: Matched pairs, as match_tables gives them
    :param prefix: Name the columns take, such as 'DZA' for 'DZAname'
    :return: Copy of the left table, with the three columns added
    """
    pairs = matches.set_index("candid")

    ids = (
        pairs["match_candid"]
        .astype("Int64")
        .reindex(left["candid"])
        .set_axis(left.index)
    )
    dists = pairs["separation"].reindex(left["candid"]).set_axis(left.index)

    return left.assign(
        **{
            f"{prefix}name": ids.map(right.set_index("candid")["objectId"]),
            f"{prefix}id": ids,
            f"{prefix}dist": dists,
        }
    )


def get_matched_ipac_table(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load the IPAC alerts of a night, with the nearest DZA source of each

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per IPAC alert
    """
    return add_matches(
        get_ipac_table(night, data_dir),
        get_dza_table(night, data_dir),
        get_ipac_matches(night, data_dir),
        "DZA",
    )


def get_matched_dza_table(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load the DZA alerts of a night, with the nearest IPAC source of each

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per DZA alert
    """
    return add_matches(
        get_dza_table(night, data_dir),
        get_ipac_table(night, data_dir),
        get_dza_matches(night, data_dir),
        "IPAC",
    )


def get_matched_pairs(
    night: str, columns: list[str], data_dir: Path | None = None
) -> pd.DataFrame:
    """
    Pair each matched IPAC alert with the DZA alert of the same source

    The pairs are taken by candid, which is unique to one alert, rather than
    by the source name, which can appear more than once in one quadrant of one
    exposure.

    :param night: Night, as a 'YYYYMMDD' string
    :param columns: Columns of each pipeline to keep, suffixed per pipeline
    :param data_dir: Path to data directory
    :return: Table with one row per matched pair
    """
    matches = get_ipac_matches(night, data_dir)
    ipac = get_ipac_table(night, data_dir).set_index("candid")
    dza = get_dza_table(night, data_dir).set_index("candid")

    pairs = pd.concat(
        [
            ipac.loc[matches["candid"], columns]
            .add_suffix("_ipac")
            .reset_index(drop=True),
            dza.loc[matches["match_candid"], columns]
            .add_suffix("_dza")
            .reset_index(drop=True),
        ],
        axis="columns",
    )
    pairs["separation"] = matches["separation"].to_numpy()

    logger.info(f"Paired {len(pairs)} alerts")

    return pairs

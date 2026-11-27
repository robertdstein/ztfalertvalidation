"""
Checks comparing the photometry of the two pipelines
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.checks.quadrants import GROUP_COLUMNS
from ztfalertvalidation.crossmatch import get_matched_pairs
from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)

MAG_COLUMNS = ["magpsf", "magap"]
PRIMARY_MAG_COLUMN = "magpsf"
DEPTH_COLUMN = "diffmaglim"
QUANTILES = [0.5, 0.9, 0.99]


def flux_ratio(delta_mag: pd.Series) -> pd.Series:
    """
    Turn a magnitude difference into a fractional difference in flux

    :param delta_mag: Difference of two magnitudes
    :return: Fractional difference of the two fluxes
    """
    return 10 ** (-0.4 * delta_mag) - 1


def get_quadrant_depth(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Get the limiting magnitude each pipeline reports for each quadrant

    Every alert of a quadrant carries the same limiting magnitude, so one
    alert of it gives the quadrant's value.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per quadrant both pipelines processed
    """
    depths = {
        "ipac": get_ipac_table(night, data_dir),
        "dza": get_dza_table(night, data_dir),
    }

    return pd.DataFrame(
        {
            name: table.groupby(GROUP_COLUMNS)[DEPTH_COLUMN].first()
            for name, table in depths.items()
        }
    ).dropna()


def compare_depth(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the limiting magnitude the two pipelines reach in each quadrant

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per quantile of the difference
    """
    depth = get_quadrant_depth(night, data_dir)
    difference = (depth["dza"] - depth["ipac"]).abs()

    table = pd.DataFrame(
        {"limiting magnitude difference": difference.quantile(QUANTILES).to_numpy()},
        index=[f"{x:.0%}" for x in QUANTILES],
    )
    table.index.name = "quantile"

    logger.info(f"Compared the depth of {len(depth)} quadrants")

    return table


def compare_photometry(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the magnitudes the two pipelines measure for a matched source

    The difference is given as a fraction of the flux, since that is how the
    requirement is set, for the psf and the aperture magnitude alike.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per quantile of the difference
    """
    pairs = get_matched_pairs(night, MAG_COLUMNS, data_dir)

    table = pd.DataFrame(
        {
            column: flux_ratio(pairs[f"{column}_dza"] - pairs[f"{column}_ipac"])
            .abs()
            .quantile(QUANTILES)
            .to_numpy()
            for column in MAG_COLUMNS
        },
        index=[f"{x:.0%}" for x in QUANTILES],
    )
    table.index.name = "quantile"

    logger.info(f"Compared the photometry of {len(pairs)} matched alerts")

    return table


def fraction_within(
    night: str, limit: float, data_dir: Path | None = None
) -> tuple[int, int]:
    """
    Count the matched alerts whose psf flux agrees to within a fraction

    :param night: Night, as a 'YYYYMMDD' string
    :param limit: Fractional difference in flux to count as agreeing
    :param data_dir: Path to data directory
    :return: The number agreeing, and the number of matched alerts
    """
    pairs = get_matched_pairs(night, [PRIMARY_MAG_COLUMN], data_dir)

    delta = pairs[f"{PRIMARY_MAG_COLUMN}_dza"] - pairs[f"{PRIMARY_MAG_COLUMN}_ipac"]
    agreeing = int((flux_ratio(delta).abs() < limit).sum())

    return agreeing, len(pairs)

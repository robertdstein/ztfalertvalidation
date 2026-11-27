"""
Check comparing the photometry of matched alerts
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.crossmatch import get_matched_pairs

logger = logging.getLogger(__name__)

MAG_COLUMN = "magpsf"
QUANTILES = [0.5, 0.9, 0.99]


def flux_ratio(delta_mag: pd.Series) -> pd.Series:
    """
    Turn a magnitude difference into a fractional difference in flux

    :param delta_mag: Difference of two magnitudes
    :return: Fractional difference of the two fluxes
    """
    return 10 ** (-0.4 * delta_mag) - 1


def compare_photometry(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the magnitude each pipeline measures for a matched source

    The difference is given as a fraction of the flux, since that is how the
    requirement is set, alongside the magnitude difference itself.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per quantile of the difference
    """
    pairs = get_matched_pairs(night, [MAG_COLUMN], data_dir)

    delta = pairs[f"{MAG_COLUMN}_dza"] - pairs[f"{MAG_COLUMN}_ipac"]
    fraction = flux_ratio(delta).abs()

    table = pd.DataFrame(
        {
            "flux difference": fraction.quantile(QUANTILES).to_numpy(),
            "magnitude difference": delta.abs().quantile(QUANTILES).to_numpy(),
        },
        index=[f"{x:.0%}" for x in QUANTILES],
    )
    table.loc["maximum"] = [fraction.max(), delta.abs().max()]
    table.index.name = "quantile"

    logger.info(f"Compared the photometry of {len(pairs)} matched alerts")

    return table


def fraction_within(
    night: str, limit: float, data_dir: Path | None = None
) -> tuple[int, int]:
    """
    Count the matched alerts whose flux agrees to within a fraction

    :param night: Night, as a 'YYYYMMDD' string
    :param limit: Fractional difference in flux to count as agreeing
    :param data_dir: Path to data directory
    :return: The number agreeing, and the number of matched alerts
    """
    pairs = get_matched_pairs(night, [MAG_COLUMN], data_dir)

    delta = pairs[f"{MAG_COLUMN}_dza"] - pairs[f"{MAG_COLUMN}_ipac"]
    agreeing = int((flux_ratio(delta).abs() < limit).sum())

    return agreeing, len(pairs)

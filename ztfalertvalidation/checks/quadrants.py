"""
Check comparing the number of alerts of each quadrant
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)

GROUP_COLUMNS = ["jd", "rcid"]
N_QUADRANTS = 64


def compare_quadrants(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the number of alerts of each quadrant

    All the alerts of one exposure share a jd, and each quadrant read out for
    that exposure has its own rcid. Every exposure gets a row per quadrant, so
    a quadrant with no alerts from either pipeline counts NA for both, while
    one that only a single pipeline produced alerts for counts zero for the
    other.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per quadrant of each exposure
    """
    counts = {
        "n_ipac": get_ipac_table(night, data_dir).value_counts(GROUP_COLUMNS),
        "n_dza": get_dza_table(night, data_dir).value_counts(GROUP_COLUMNS),
    }

    df = pd.DataFrame(counts)

    quadrants = pd.MultiIndex.from_product(
        [df.index.get_level_values("jd").unique().sort_values(), range(N_QUADRANTS)],
        names=GROUP_COLUMNS,
    )
    df = df.reindex(quadrants)

    seen = df.notna().any(axis="columns")
    df[seen] = df[seen].fillna(0)

    logger.info(f"Found {len(df)} quadrants over {df.index.levshape[0]} exposures")

    return df.astype("Int64")

"""
Check comparing the number of alerts of each exposure quadrant
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)

GROUP_COLUMNS = ["jd", "rcid"]


def compare_exposures(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the number of alerts of each exposure quadrant

    All the alerts of one exposure share a jd, and each quadrant read out for
    that exposure has its own rcid. A quadrant missing from a pipeline counts
    zero alerts there.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per exposure quadrant
    """
    counts = {
        "n_ipac": get_ipac_table(night, data_dir).value_counts(GROUP_COLUMNS),
        "n_dza": get_dza_table(night, data_dir).value_counts(GROUP_COLUMNS),
    }

    df = pd.DataFrame(counts).fillna(0).astype(int).sort_index()

    logger.info(f"Found {len(df)} exposure quadrants")

    return df

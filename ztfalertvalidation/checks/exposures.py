"""
Check comparing the number of alerts of each exposure
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)


def compare_exposures(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the number of alerts of each exposure

    All the alerts of one exposure share a jd, so the alerts are grouped by
    that. An exposure missing from a pipeline counts zero alerts there.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per exposure
    """
    counts = {
        "n_ipac": get_ipac_table(night, data_dir)["jd"].value_counts(),
        "n_dza": get_dza_table(night, data_dir)["jd"].value_counts(),
    }

    df = pd.DataFrame(counts).fillna(0).astype(int).sort_index()
    df.index.name = "jd"

    logger.info(f"Found {len(df)} exposures")

    return df

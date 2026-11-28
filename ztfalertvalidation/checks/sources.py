"""
Check comparing how the two pipelines name their sources
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.checks.quadrants import GROUP_COLUMNS
from ztfalertvalidation.crossmatch import get_matched_pairs
from ztfalertvalidation.tables import get_dza_table, get_ipac_table

logger = logging.getLogger(__name__)

NAME_COLUMN = "objectId"


def count_repeated_sources(table: pd.DataFrame) -> tuple[int, int]:
    """
    Count the sources a pipeline names twice in one exposure quadrant

    One source lies at one position of one readout, so it should raise at most
    one alert there.

    :param table: Table of a pipeline's alerts
    :return: The number of sources, and the alerts they account for
    """
    per_quadrant = table.groupby(GROUP_COLUMNS + [NAME_COLUMN]).size()
    repeated = per_quadrant[per_quadrant > 1]

    return len(repeated), int(repeated.sum())


def compare_sources(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare how the two pipelines name the sources of a night

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per count, with a column per pipeline
    """
    tables = {
        "IPAC": get_ipac_table(night, data_dir),
        "DZA": get_dza_table(night, data_dir),
    }
    pairs = get_matched_pairs(night, [NAME_COLUMN], data_dir)

    names = {
        "IPAC": pairs.groupby(f"{NAME_COLUMN}_ipac")[f"{NAME_COLUMN}_dza"].nunique(),
        "DZA": pairs.groupby(f"{NAME_COLUMN}_dza")[f"{NAME_COLUMN}_ipac"].nunique(),
    }

    counts = {}
    for pipeline, table in tables.items():
        sources, alerts = count_repeated_sources(table)
        counts[pipeline] = [
            len(table),
            table[NAME_COLUMN].nunique(),
            sources,
            alerts,
            len(names[pipeline]),
            int((names[pipeline] > 1).sum()),
        ]

    logger.info(
        f"IPAC names {counts['IPAC'][2]} sources twice in one quadrant, "
        f"DZA {counts['DZA'][2]}"
    )

    return pd.DataFrame(
        counts,
        index=[
            "alerts",
            "sources named",
            "sources named twice in one quadrant",
            "alerts those account for",
            "sources matched to the other pipeline",
            "of those, matched to more than one name",
        ],
    )

"""
Check comparing the columns the two pipelines write
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.paths import get_dza_dir, get_ipac_dir
from ztfalertvalidation.schema import get_fields

logger = logging.getLogger(__name__)


def compare_columns(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the columns of the two pipelines, by the schema of their alerts

    An alert carries the schema it was written with, so the columns and their
    types come from the alerts themselves rather than from a published one.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per column of either pipeline
    """
    ipac = get_fields(get_ipac_dir(night, data_dir))
    dza = get_fields(get_dza_dir(night, data_dir))

    columns = ipac.index.union(dza.index, sort=False)
    table = pd.DataFrame(
        {
            "ipac": ipac["type"].reindex(columns),
            "dza": dza["type"].reindex(columns),
            "description": ipac["description"]
            .reindex(columns)
            .fillna(dza["description"].reindex(columns)),
        }
    )
    table["agrees"] = table["ipac"].eq(table["dza"]) & table["ipac"].notna()

    logger.info(f"{int(table['agrees'].sum())} of {len(table)} columns agree")

    return table

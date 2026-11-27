"""
Scripts for caching the alerts of a night as a table
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.avro import load_alerts
from ztfalertvalidation.paths import get_dza_dir, get_ipac_dir, get_night_dir

logger = logging.getLogger(__name__)


def load_cached_table(alert_dir: Path, table_path: Path) -> pd.DataFrame:
    """
    Load a table of alerts, reading the alerts themselves only once

    Reading a night of avro files takes minutes, so the table is written to
    parquet and read back from there. Delete the parquet file to rebuild it.

    :param alert_dir: Directory of avro alerts
    :param table_path: Parquet file caching the table
    :return: Table with one row per alert
    """
    if table_path.exists():
        logger.info(f"Reading cached table from {table_path}")
        return pd.read_parquet(table_path)

    df = load_alerts(alert_dir)

    logger.info(f"Caching table to {table_path}")
    df.to_parquet(table_path)

    return df


def get_dza_table(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load the table of DZA alerts of a night

    The alerts carry a ZTF object name, which is renamed to a DZA one so that
    the sources of the two pipelines cannot be confused.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per alert
    """
    df = load_cached_table(
        get_dza_dir(night, data_dir),
        get_night_dir(night, data_dir) / "dza.parquet",
    )
    df["objectId"] = df["objectId"].str.replace("^ZTF", "DZA", regex=True)
    return df


def get_ipac_table(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load the table of IPAC alerts of a night

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per alert
    """
    return load_cached_table(
        get_ipac_dir(night, data_dir),
        get_night_dir(night, data_dir) / "ipac.parquet",
    )

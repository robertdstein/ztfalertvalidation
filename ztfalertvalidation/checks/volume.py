"""
Check comparing the number of alerts and the volume of data
"""

import logging
from pathlib import Path

import pandas as pd

from ztfalertvalidation.paths import get_dza_dir, get_ipac_dir

logger = logging.getLogger(__name__)


def compare_volume(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the number of alerts and the volume of data in each pipeline

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table with one row per pipeline
    """
    rows = []

    for pipeline, alert_dir in [
        ("dza", get_dza_dir(night, data_dir)),
        ("ipac", get_ipac_dir(night, data_dir)),
    ]:
        sizes = [x.stat().st_size for x in alert_dir.glob("*.avro")]

        if len(sizes) == 0:
            err = f"Found no avro alerts in '{alert_dir}'"
            logger.error(err)
            raise FileNotFoundError(err)

        rows.append(
            {
                "pipeline": pipeline,
                "n_alerts": len(sizes),
                "volume_gb": sum(sizes) / 1e9,
                "mean_alert_kb": sum(sizes) / len(sizes) / 1e3,
            }
        )

    return pd.DataFrame(rows).set_index("pipeline")

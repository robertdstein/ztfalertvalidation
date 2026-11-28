"""
Check comparing the value of each column between the two pipelines
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ztfalertvalidation.crossmatch import get_matched_pairs
from ztfalertvalidation.paths import get_ipac_dir
from ztfalertvalidation.schema import get_fields

logger = logging.getLogger(__name__)

DECIMAL_PLACES = 3
AGREEMENT_LABEL = f"within {DECIMAL_PLACES} d.p."
DIFFERENCE_QUANTILE = 0.99
DIFFERENCE_LABEL = "99th percentile difference"
KEY_COLUMNS = ["candid", "objectId"]


def agreement_of(left: pd.Series, right: pd.Series) -> dict[str, float]:
    """
    Measure how closely one column of two pipelines agrees

    A column of numbers counts as agreeing when both values round to the same
    number of decimal places, and any other column when the two are equal,
    which is what rounding would come to.

    :param left: Column of one pipeline
    :param right: Column of the other
    :return: The agreement, as the report shows it
    """
    both = left.notna() & right.notna()
    row: dict[str, float] = {"compared": float(both.sum())}
    unmeasured = {"median difference": float("nan"), DIFFERENCE_LABEL: float("nan")}

    if both.sum() == 0:
        return row | unmeasured | {AGREEMENT_LABEL: float("nan")}

    if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
        a = left[both].to_numpy(dtype="float64")
        b = right[both].to_numpy(dtype="float64")
        difference = np.abs(a - b)

        agreeing = np.round(a, DECIMAL_PLACES) == np.round(b, DECIMAL_PLACES)

        return row | {
            "median difference": float(np.median(difference)),
            DIFFERENCE_LABEL: float(np.quantile(difference, DIFFERENCE_QUANTILE)),
            AGREEMENT_LABEL: float(np.mean(agreeing)),
        }

    equal = float((left[both] == right[both]).mean())

    return row | unmeasured | {AGREEMENT_LABEL: equal}


def compare_values(night: str, data_dir: Path | None = None) -> pd.DataFrame:
    """
    Compare the value of every column, over the matched alerts of a night

    The candid and the object name are left out: the candid is the key the
    alerts are paired by, and the two pipelines name a source differently by
    design, so neither says anything about how they agree.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Table of one row per column
    """
    fields = get_fields(get_ipac_dir(night, data_dir))
    columns = [x for x in fields.index if x not in KEY_COLUMNS]

    pairs = get_matched_pairs(night, columns, data_dir)

    table = pd.DataFrame(
        [
            agreement_of(pairs[f"{column}_ipac"], pairs[f"{column}_dza"])
            for column in columns
        ],
        index=pd.Index(columns, name="column"),
    )
    table["compared"] = table["compared"].astype("int64")

    logger.info(f"Compared {len(columns)} columns over {len(pairs)} matched alerts")

    return table.join(fields["description"])

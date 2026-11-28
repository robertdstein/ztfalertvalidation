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

DECIMAL_PLACES = [2, 3]
AGREEMENT_LABELS = {x: f"within {x} d.p." for x in DECIMAL_PLACES}

# the loosest of them is the one the report sorts and colours by
AGREEMENT_LABEL = AGREEMENT_LABELS[min(DECIMAL_PLACES)]

# the two pipelines do not share a history, so the columns counting back over
# one are not checked until they do. jdendhist is not among them: it is the
# epoch of the latest detection, which both pipelines see
CHECK_HISTORY = False
HISTORY_GROUP = "history"
HISTORY_COLUMNS = ["ncovhist", "ndethist", "jdstarthist"]

# named for the nearest solar system object, unlike ssnrms, which is a ratio
SOLAR_SYSTEM_GROUP = "solar system"
SOLAR_SYSTEM_COLUMNS = ["ssdistnr", "ssmagnr", "ssnamenr"]
DIFFERENCE_QUANTILE = 0.99
DIFFERENCE_LABEL = "99th percentile difference"
KEY_COLUMNS = ["candid", "objectId"]


def group_of(column: str) -> str:
    """
    Get the group a column is reported in

    :param column: Name of the column
    :return: Name of its group, or an empty string for the main table
    """
    if column in HISTORY_COLUMNS:
        return HISTORY_GROUP

    if column in SOLAR_SYSTEM_COLUMNS:
        return SOLAR_SYSTEM_GROUP

    return ""


def agreement_of(left: pd.Series, right: pd.Series) -> dict[str, float]:
    """
    Measure how closely one column of two pipelines agrees

    A column of numbers counts as agreeing when both values round to the same
    value at a number of decimal places, and any other column when the two
    are equal, which is what rounding would come to.

    :param left: Column of one pipeline
    :param right: Column of the other
    :return: The agreement, as the report shows it
    """
    both = left.notna() & right.notna()
    row: dict[str, float] = {"compared": float(both.sum())}
    unmeasured = {"median difference": float("nan"), DIFFERENCE_LABEL: float("nan")}

    if both.sum() == 0:
        return row | unmeasured | {x: float("nan") for x in AGREEMENT_LABELS.values()}

    if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
        a = left[both].to_numpy(dtype="float64")
        b = right[both].to_numpy(dtype="float64")
        difference = np.abs(a - b)

        return (
            row
            | {
                "median difference": float(np.median(difference)),
                DIFFERENCE_LABEL: float(np.quantile(difference, DIFFERENCE_QUANTILE)),
            }
            | {
                label: float(np.mean(np.round(a, places) == np.round(b, places)))
                for places, label in AGREEMENT_LABELS.items()
            }
        )

    equal = float((left[both] == right[both]).mean())

    return row | unmeasured | {x: equal for x in AGREEMENT_LABELS.values()}


def compare_values(
    night: str,
    data_dir: Path | None = None,
    check_history: bool = CHECK_HISTORY,
) -> pd.DataFrame:
    """
    Compare the value of every column, over the matched alerts of a night

    The candid and the object name are left out: the candid is the key the
    alerts are paired by, and the two pipelines name a source differently by
    design, so neither says anything about how they agree. A column counting
    back over the survey is measured but not counted as checked, unless the
    two pipelines are known to share a history.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :param check_history: Whether a history column counts as checked
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
    table["group"] = [group_of(x) for x in columns]
    table["checked"] = check_history | (table["group"] != HISTORY_GROUP)

    logger.info(f"Compared {len(columns)} columns over {len(pairs)} matched alerts")

    return table.join(fields["description"])

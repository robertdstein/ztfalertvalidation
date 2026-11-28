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

SIGNIFICANT_FIGURES = [3, 5]
KEY_COLUMNS = ["candid", "objectId"]


def round_to_significant(values: np.ndarray, digits: int) -> np.ndarray:
    """
    Round values to a number of significant figures

    :param values: Values to round
    :param digits: Significant figures to keep
    :return: The rounded values
    """
    out = np.asarray(values, dtype="float64")
    scale = np.zeros_like(out)

    usable = np.isfinite(out) & (out != 0)
    scale[usable] = digits - 1 - np.floor(np.log10(np.abs(out[usable])))

    return np.where(usable, np.round(out * 10.0**scale) / 10.0**scale, out)


def agreement_of(left: pd.Series, right: pd.Series) -> dict[str, float]:
    """
    Measure how closely one column of two pipelines agrees

    A column of numbers is compared by rounding both to a number of
    significant figures, and any other column by equality, which is what
    rounding would come to.

    :param left: Column of one pipeline
    :param right: Column of the other
    :return: The agreement, as the report shows it
    """
    both = left.notna() & right.notna()
    row: dict[str, float] = {"compared": float(both.sum())}

    if both.sum() == 0:
        return (
            row
            | {"median difference": float("nan")}
            | {f"within {x} s.f.": float("nan") for x in SIGNIFICANT_FIGURES}
        )

    if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
        a = left[both].to_numpy(dtype="float64")
        b = right[both].to_numpy(dtype="float64")

        row["median difference"] = float(np.median(np.abs(a - b)))
        for digits in SIGNIFICANT_FIGURES:
            rounded = round_to_significant(a, digits)
            agreeing = rounded == round_to_significant(b, digits)
            row[f"within {digits} s.f."] = float(np.mean(agreeing))

        return row

    equal = float((left[both] == right[both]).mean())
    return (
        row
        | {"median difference": float("nan")}
        | {f"within {x} s.f.": equal for x in SIGNIFICANT_FIGURES}
    )


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

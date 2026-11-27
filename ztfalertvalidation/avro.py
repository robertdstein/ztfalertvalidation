"""
Scripts for reading avro alerts
"""

import logging
from pathlib import Path

import pandas as pd
from fastavro import reader
from tqdm import tqdm

logger = logging.getLogger(__name__)

DROPPED_FIELDS = [
    "candidate",
    "prv_candidates",
    "fp_hists",
    "cutoutScience",
    "cutoutTemplate",
    "cutoutDifference",
]


def load_avro(avro_path: Path) -> list[dict]:
    """
    Load the records of an avro file

    fastavro types a record as a wide union of everything avro can hold, so
    this narrows them to the records callers expect.

    :param avro_path: Avro file to load
    :return: Records in the file
    """
    records: list[dict] = []

    with open(avro_path, "rb") as avro_f:
        for record in reader(avro_f):
            if not isinstance(record, dict):
                err = (
                    f"Expected records in '{avro_path}', "
                    f"but found a {type(record).__name__}"
                )
                logger.error(err)
                raise ValueError(err)
            records.append(record)

    return records


def unpack_record(record: dict) -> dict:
    """
    Unpack an alert record into one flat row

    The candidate fields are raised to the top level, alongside the alert's
    object and candidate ids. The cutouts, the previous candidates and the
    forced photometry history are dropped, since they do not fit in a column.

    :param record: Alert record
    :return: Row of alert values
    """
    row = {x: y for x, y in record.items() if x not in DROPPED_FIELDS}
    return row | record["candidate"]


def load_alerts(alert_dir: Path) -> pd.DataFrame:
    """
    Load every avro alert in a directory

    :param alert_dir: Directory of avro alerts
    :return: Table with one row per alert
    """
    avro_paths = sorted(alert_dir.glob("*.avro"))

    if len(avro_paths) == 0:
        err = f"Found no avro files in '{alert_dir}'"
        logger.error(err)
        raise FileNotFoundError(err)

    logger.info(f"Found {len(avro_paths)} avro files in {alert_dir}")

    rows = []
    for avro_path in tqdm(avro_paths, unit="alert"):
        rows += [unpack_record(x) for x in load_avro(avro_path)]

    logger.info(f"Loaded {len(rows)} alerts")

    return pd.DataFrame(rows)

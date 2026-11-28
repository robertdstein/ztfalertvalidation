"""
Scripts for reading the schema the alerts of a pipeline were written with
"""

import logging
from pathlib import Path

import pandas as pd
from fastavro import reader

from ztfalertvalidation.avro import DROPPED_FIELDS

logger = logging.getLogger(__name__)

CANDIDATE_FIELD = "candidate"


def load_alert_schema(alert_dir: Path) -> dict:
    """
    Load the schema the alerts of a directory were written with

    Every alert of a night shares one schema, so the first file gives it.

    :param alert_dir: Directory of avro alerts
    :return: Schema of an alert
    """
    paths = sorted(alert_dir.glob("*.avro"))

    if len(paths) == 0:
        err = f"Found no avro files in '{alert_dir}'"
        logger.error(err)
        raise FileNotFoundError(err)

    with open(paths[0], "rb") as avro_f:
        schema = reader(avro_f).writer_schema

    if not isinstance(schema, dict):
        err = (
            f"Expected a record schema in '{paths[0]}', "
            f"but found a {type(schema).__name__}"
        )
        logger.error(err)
        raise ValueError(err)

    return schema


def get_fields(alert_dir: Path) -> pd.DataFrame:
    """
    Get the field of each column of the table an alert is unpacked into

    The candidate fields are raised to the top level, as unpack_record does,
    and the fields it drops are left out.

    :param alert_dir: Directory of avro alerts
    :return: Table of one row per column, with its type and description
    """
    schema = load_alert_schema(alert_dir)

    fields: dict[str, dict] = {}
    for field in schema["fields"]:
        if field["name"] == CANDIDATE_FIELD:
            fields |= {x["name"]: x for x in field["type"]["fields"]}
        elif field["name"] not in DROPPED_FIELDS:
            fields[field["name"]] = field

    return pd.DataFrame(
        {
            "type": [str(x["type"]) for x in fields.values()],
            "description": [x.get("doc", "") for x in fields.values()],
        },
        index=pd.Index(list(fields), name="column"),
    )

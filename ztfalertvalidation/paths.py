"""
Scripts for handling paths to alert directories

The alerts are expected to be laid out as one directory per night, each
containing one subdirectory per pipeline::

    $ZTFALERTVALIDATION_DATA_DIR/
        <night>/
            dza/                      # DZA pipeline alerts
            ztf_public_<YYYYMMDD>/    # Official IPAC pipeline alerts

A night is selected by the name of its directory, as listed by `list_nights`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR_KEY = "ZTFALERTVALIDATION_DATA_DIR"
DZA_DIR_NAME = "dza"
IPAC_DIR_PATTERN = "ztf_public_*"


def get_data_dir(data_dir: Path | str | None = None) -> Path:
    """
    Get path to the parent data directory

    :param data_dir: Path to data directory
    :return: Path to data directory
    """
    _data_dir = data_dir or os.getenv(DATA_DIR_KEY)
    if _data_dir is None:
        raise ValueError(f"'{DATA_DIR_KEY}' environment variable not set")
    return Path(_data_dir).expanduser()


def list_nights(data_dir: Path | str | None = None) -> list[str]:
    """
    List the nights available in the data directory

    :param data_dir: Path to data directory
    :return: Names of the night directories
    """
    return sorted(x.name for x in get_data_dir(data_dir).iterdir() if x.is_dir())


def get_night_dir(night: str, data_dir: Path | str | None = None) -> Path:
    """
    Get path to the directory of a night

    :param night: Name of the night directory
    :param data_dir: Path to data directory
    :return: Path to night directory
    """
    path = get_data_dir(data_dir) / night
    if not path.is_dir():
        raise FileNotFoundError(
            f"Found no directory for night '{night}', "
            f"available nights are {list_nights(data_dir)}"
        )
    return path


def get_dza_dir(night: str, data_dir: Path | str | None = None) -> Path:
    """
    Get path to the DZA alerts of a night

    :param night: Name of the night directory
    :param data_dir: Path to data directory
    :return: Path to DZA alert directory
    """
    return get_night_dir(night, data_dir) / DZA_DIR_NAME


def get_ipac_dir(night: str, data_dir: Path | str | None = None) -> Path:
    """
    Get path to the IPAC alerts of a night

    :param night: Name of the night directory
    :param data_dir: Path to data directory
    :return: Path to IPAC alert directory
    """
    night_dir = get_night_dir(night, data_dir)
    matches = sorted(night_dir.glob(IPAC_DIR_PATTERN))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected one '{IPAC_DIR_PATTERN}' directory in '{night_dir}', "
            f"found {[x.name for x in matches]}"
        )
    return matches[0]

"""
Scripts for downloading the public alerts of a night
"""

import logging
import tarfile
import urllib.request
from pathlib import Path

from tqdm import tqdm

from ztfalertvalidation.paths import IPAC_DIR_PREFIX, get_data_dir

logger = logging.getLogger(__name__)

PUBLIC_ALERT_URL = "https://ztf.uw.edu/alerts/public"
CHUNK_SIZE = 1024 * 1024
TIMEOUT = 60


def get_ipac_url(night: str) -> str:
    """
    Get the url of the public IPAC alerts of a night

    :param night: Night, as a 'YYYYMMDD' string
    :return: Url of the tarball of alerts
    """
    if not (len(night) == 8 and night.isdigit()):
        err = f"Expected a night in 'YYYYMMDD' format, but got '{night}'"
        logger.error(err)
        raise ValueError(err)

    return f"{PUBLIC_ALERT_URL}/{IPAC_DIR_PREFIX}{night}.tar.gz"


def download_file(url: str, path: Path) -> None:
    """
    Download a url to a file

    :param url: Url to download
    :param path: Path of the file to write
    :return: None
    """
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        size = int(response.headers.get("Content-Length", 0))

        with (
            open(path, "wb") as out,
            tqdm(total=size, unit="B", unit_scale=True) as progress,
        ):
            while chunk := response.read(CHUNK_SIZE):
                out.write(chunk)
                progress.update(len(chunk))


def unpack_alerts(tarball: Path, alert_dir: Path) -> None:
    """
    Unpack a tarball of alerts into a directory

    The tarball holds the avro files at its root, and is unpacked with the
    'data' filter, so an entry pointing outside the directory is refused.

    :param tarball: Tarball of alerts
    :param alert_dir: Directory to unpack into
    :return: None
    """
    alert_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tarball) as tar:
        tar.extractall(alert_dir, filter="data")


def download_ipac_alerts(night: str, data_dir: Path | None = None) -> Path:
    """
    Download the public IPAC alerts of a night, unless they are already there

    The tarball is removed once it is unpacked, since the alerts themselves
    take more space again and the tarball can be fetched anew.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :return: Path to the directory of alerts
    """
    url = get_ipac_url(night)
    alert_dir = get_data_dir(data_dir) / night / f"{IPAC_DIR_PREFIX}{night}"

    if any(alert_dir.glob("*.avro")):
        logger.info(f"Found alerts in {alert_dir} already")
        return alert_dir

    tarball = alert_dir.with_suffix(".tar.gz")
    tarball.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading {url}")
    download_file(url, tarball)

    logger.info(f"Unpacking {tarball} into {alert_dir}")
    unpack_alerts(tarball, alert_dir)
    tarball.unlink()

    logger.info(f"Unpacked {len(list(alert_dir.glob('*.avro')))} alerts")

    return alert_dir

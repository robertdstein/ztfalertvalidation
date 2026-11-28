"""
Scripts for plotting the contents of an alert
"""

import gzip
import io
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from astropy import visualization
from astropy.io import fits
from matplotlib.colors import Normalize
from matplotlib.figure import Figure

from ztfalertvalidation.avro import load_avro
from ztfalertvalidation.crossmatch import get_ipac_matches
from ztfalertvalidation.paths import get_dza_dir, get_ipac_dir
from ztfalertvalidation.tables import get_dza_table, get_ipac_table, rename_dza

logger = logging.getLogger(__name__)

CUTOUTS = ["Science", "Template", "Difference"]
FILTERS = {1: ("g", "green"), 2: ("r", "red"), 3: ("i", "orange")}
KEY_FIELDS = [
    "jd",
    "fid",
    "ra",
    "dec",
    "magpsf",
    "sigmapsf",
    "magap",
    "rb",
    "drb",
    "ndethist",
]
FIELD_FORMATS = {"jd": ".5f", "ra": ".6f", "dec": ".6f"}
DEFAULT_FORMAT = ".4f"
MJD_OFFSET = 2400000.5


def load_cutout(record: dict, kind: str) -> np.ndarray:
    """
    Load one cutout of an alert as an image

    :param record: Alert record
    :param kind: Cutout to load, such as 'Science'
    :return: The image
    """
    stamp = record[f"cutout{kind}"]["stampData"]

    with gzip.open(io.BytesIO(stamp), "rb") as gz_f:
        image = fits.getdata(io.BytesIO(gz_f.read()), ignore_missing_simple=True)

    return np.asarray(image, dtype="float64")


def plot_cutout(axis: plt.Axes, image: np.ndarray, title: str) -> None:
    """
    Plot one cutout, stretched so that the source is visible

    :param axis: Axis to plot on
    :param image: Image to plot
    :param title: Title of the cutout
    :return: None
    """
    finite = image[np.isfinite(image)]
    low, high = np.percentile(finite, [0, 100]) if len(finite) else (0.0, 1.0)
    stretched = visualization.AsinhStretch()((image - low) / (high - low))

    shown = stretched[np.isfinite(stretched)]
    axis.imshow(
        stretched,
        norm=Normalize(*np.percentile(shown, [0.5, 99.5])) if len(shown) else None,
        cmap="gray",
        origin="lower",
    )
    axis.set_title(title, fontsize="small")
    axis.set_xticks([])
    axis.set_yticks([])


def get_lightcurve(record: dict) -> pd.DataFrame:
    """
    Get the photometry of an alert, from the alert and its previous candidates

    :param record: Alert record
    :return: Table of one row per epoch
    """
    epochs = [record["candidate"]] + list(record["prv_candidates"] or [])

    table = pd.DataFrame(epochs)
    table["mjd"] = table["jd"] - MJD_OFFSET
    table["detection"] = table["magpsf"].notna()

    return table.sort_values("mjd")


def plot_lightcurve(axis: plt.Axes, record: dict) -> None:
    """
    Plot the photometry of an alert, with the upper limits of its non-detections

    :param axis: Axis to plot on
    :param record: Alert record
    :return: None
    """
    table = get_lightcurve(record)
    latest = record["candidate"]["jd"] - MJD_OFFSET

    for fid, (name, colour) in FILTERS.items():
        band = table[table["fid"] == fid]

        detected = band[band["detection"]]
        if len(detected):
            axis.errorbar(
                detected["mjd"],
                detected["magpsf"],
                yerr=detected["sigmapsf"],
                fmt="o",
                color=colour,
                label=f"{name} detection",
                markersize=4,
            )

        limits = band[~band["detection"]]
        if len(limits):
            axis.scatter(
                limits["mjd"],
                limits["diffmaglim"],
                marker="v",
                color=colour,
                alpha=0.3,
                s=14,
                label=f"{name} limit",
            )

    axis.axvline(latest, color="grey", linestyle=":", linewidth=1)
    axis.invert_yaxis()
    axis.set_xlabel("MJD")
    axis.set_ylabel("magnitude")
    axis.legend(fontsize="x-small", ncol=2, loc="lower left")


def format_field(record: dict, field: str) -> str:
    """
    Render one field of an alert

    :param record: Alert record
    :param field: Field to render
    :return: The value, as the table shows it
    """
    value = record["candidate"].get(field)

    if not isinstance(value, float):
        return str(value)

    return f"{value:{FIELD_FORMATS.get(field, DEFAULT_FORMAT)}}"


def plot_fields(axis: plt.Axes, record: dict) -> None:
    """
    Tabulate the fields of an alert worth seeing beside its plots

    :param axis: Axis to plot on
    :param record: Alert record
    :return: None
    """
    axis.axis("off")

    table = axis.table(
        cellText=[[x, format_field(record, x)] for x in KEY_FIELDS],
        colLabels=["field", "value"],
        colWidths=[0.42, 0.58],
        cellLoc="left",
        colLoc="left",
        loc="center",
        edges="horizontal",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1, 1.15)


def find_matched_pair(
    night: str, data_dir: Path | None = None, min_detections: int = 2
) -> tuple[int, int]:
    """
    Pick a matched pair of alerts to plot

    Both pipelines must give the alert the same history, so that the two
    lightcurves are comparable, and the pair with the longest history is
    taken.

    :param night: Night, as a 'YYYYMMDD' string
    :param data_dir: Path to data directory
    :param min_detections: Fewest prior detections the pair may have
    :return: The candid of the IPAC alert and of the DZA one
    """
    matches = get_ipac_matches(night, data_dir)
    ipac = get_ipac_table(night, data_dir).set_index("candid")
    dza = get_dza_table(night, data_dir).set_index("candid")

    history = ["ndethist", "jdstarthist"]
    left = ipac.loc[matches["candid"], history].reset_index(drop=True)
    right = dza.loc[matches["match_candid"], history].reset_index(drop=True)

    same = (left == right).all(axis="columns") & (left["ndethist"] >= min_detections)

    if not same.any():
        err = (
            f"Found no matched pair of {night} whose history agrees, with at "
            f"least {min_detections} detections"
        )
        logger.error(err)
        raise ValueError(err)

    row = left[same]["ndethist"].idxmax()
    logger.info(f"Picked a pair with ndethist {left['ndethist'].iloc[row]}")

    return matches["candid"].iloc[row], matches["match_candid"].iloc[row]


def plot_alert_pair(
    night: str,
    path: Path,
    candids: tuple[int, int] | None = None,
    data_dir: Path | None = None,
) -> tuple[int, int]:
    """
    Plot an alert of each pipeline for the same source, one above the other

    :param night: Night, as a 'YYYYMMDD' string
    :param path: Path of the image to write
    :param candids: The pair to plot, or the longest history by default
    :param data_dir: Path to data directory
    :return: The candid of the IPAC alert and of the DZA one
    """
    pair = candids or find_matched_pair(night, data_dir)

    alerts = {
        "IPAC": load_avro(get_ipac_dir(night, data_dir) / f"{pair[0]}.avro")[0],
        "DZA": load_avro(get_dza_dir(night, data_dir) / f"{pair[1]}.avro")[0],
    }

    figure: Figure = plt.figure(figsize=(13, 7.5))
    grid = figure.add_gridspec(
        2,
        3,
        width_ratios=[1.25, 3, 2.9],
        hspace=0.4,
        wspace=0.3,
        top=0.86,
        bottom=0.09,
        left=0.04,
        right=0.98,
    )

    alerts["DZA"]["objectId"] = rename_dza(alerts["DZA"]["objectId"])

    for row, (pipeline, record) in enumerate(alerts.items()):
        plot_fields(figure.add_subplot(grid[row, 0]), record)

        cutouts = grid[row, 1].subgridspec(1, len(CUTOUTS), wspace=0.06)
        for column, kind in enumerate(CUTOUTS):
            plot_cutout(
                figure.add_subplot(cutouts[0, column]), load_cutout(record, kind), kind
            )

        plot_lightcurve(figure.add_subplot(grid[row, 2]), record)

        figure.text(
            0.04,
            0.915 - row * 0.465,
            f"{pipeline}   {record['objectId']}   candid {record['candid']}",
            fontsize="medium",
            fontweight="bold",
        )

    figure.suptitle(f"Alert pair of {night}", fontsize="large", y=0.98)
    figure.savefig(path, dpi=130)
    plt.close(figure)

    logger.info(f"Wrote {path}")

    return pair

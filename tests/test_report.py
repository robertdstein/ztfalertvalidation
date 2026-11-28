"""
Tests for reporting the result of each check
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import fastavro
import pandas as pd

from ztfalertvalidation import (
    Section,
    build_summary,
    get_programids,
    render_html,
    write_html_report,
)
from ztfalertvalidation.report import quadrant_section

NIGHT = "20261112"

CANDIDATE_FIELDS = [
    ("jd", "double", "Observation Julian date at start of exposure [days]"),
    ("rcid", "int", "Readout channel ID [00 .. 63]"),
    ("ra", "double", "Right Ascension of candidate [deg]"),
    ("dec", "double", "Declination of candidate [deg]"),
    ("programid", "int", "Program ID"),
    ("magpsf", "float", "Magnitude from PSF-fit photometry [mag]"),
    ("magap", "float", "Aperture mag using 14 pixel diameter aperture [mag]"),
    ("diffmaglim", "float", "Expected 5-sigma mag limit in difference image"),
]

SCHEMA = {
    "type": "record",
    "name": "ztf.alert",
    "fields": [
        {"name": "objectId", "type": "string", "doc": "object identifier"},
        {"name": "candid", "type": "long", "doc": "Candidate ID"},
        {
            "name": "candidate",
            "type": {
                "type": "record",
                "name": "ztf.alert.candidate",
                "fields": [
                    {"name": name, "type": kind, "doc": doc}
                    for name, kind, doc in CANDIDATE_FIELDS
                ],
            },
        },
    ],
}

ALERTS: dict[str, dict[str, list]] = {
    "ipac": {
        "objectId": ["ZTF00a", "ZTF00b"],
        "candid": [1, 2],
        "jd": [1.0, 1.0],
        "rcid": [8, 8],
        "ra": [10.0, 10.1],
        "dec": [20.0, 20.0],
        "programid": [1, 1],
        "magpsf": [19.5, 18.0],
        "magap": [19.6, 18.1],
        "diffmaglim": [20.3, 20.3],
    },
    "dza": {
        "objectId": ["ZTF00x"],
        "candid": [10],
        "jd": [1.0],
        "rcid": [8],
        "ra": [10.0],
        "dec": [20.0],
        "programid": [1],
        "magpsf": [19.5],
        "magap": [19.6],
        "diffmaglim": [20.3],
    },
}


def write_alert(path: Path, values: dict[str, list], row: int) -> None:
    """
    Write one alert, so that the schema of the night can be read from it

    :param path: Avro file to write
    :param values: Columns of the pipeline's alerts
    :param row: Row of those columns to write
    :return: None
    """
    record = {
        "objectId": values["objectId"][row],
        "candid": values["candid"][row],
        "candidate": {name: values[name][row] for name, _, _ in CANDIDATE_FIELDS},
    }

    with open(path, "wb") as avro_f:
        fastavro.writer(avro_f, SCHEMA, [record])


def build_example(data_dir: Path) -> None:
    """
    Write a night of cached tables, and the avro files the checks read

    :param data_dir: Path to data directory
    :return: None
    """
    night_dir = data_dir / NIGHT
    alert_dirs = {"dza": night_dir / "dza", "ipac": night_dir / f"ztf_public_{NIGHT}"}

    for pipeline, values in ALERTS.items():
        alert_dirs[pipeline].mkdir(parents=True)
        for row, name in enumerate(values["objectId"]):
            write_alert(alert_dirs[pipeline] / f"{name}.avro", values, row)
        pd.DataFrame(values).to_parquet(night_dir / f"{pipeline}.parquet")


class TestReport(unittest.TestCase):
    """Tests for reporting the result of each check"""

    def test_write_html_report(self):
        """Test that a report of a night holds a section per check"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            build_example(data_dir)
            path = data_dir / "report.html"

            write_html_report(NIGHT, path, data_dir)
            page = path.read_text()

            for title in [
                "Alert volume",
                "Quadrant coverage",
                "Asymmetric processing failures",
                "Source crossmatch",
            ]:
                self.assertIn(title, page)

            self.assertIn("Astrometric precision", page)
            self.assertIn("Alert columns", page)
            self.assertIn("Column agreement", page)
            self.assertIn("Limiting magnitude", page)
            self.assertIn("PSF photometry", page)
            self.assertIn("Aperture photometry", page)
            self.assertIn(NIGHT, page)
            self.assertIn("programid 1", page)

            # each section ends in its take-home message
            self.assertEqual(page.count('class="message"'), 10)

    def test_summary_collects_the_sections(self):
        """Test that the summary holds the night and each section's numbers"""
        sections = [
            Section("First", "", pd.DataFrame(), {"One": "1"}, ""),
            Section("Second", "", pd.DataFrame(), {"Two": "2"}, ""),
        ]

        summary = build_summary(sections, NIGHT)

        self.assertEqual(list(summary.index), ["Night", "One", "Two"])
        self.assertEqual(list(summary["value"]), [NIGHT, "1", "2"])

    def test_render_html_is_self_contained(self):
        """Test that the page needs nothing fetched to read it"""
        section = Section("Only", "Some prose", pd.DataFrame(), {}, "A take-home")
        page = render_html([section], NIGHT, [1])

        self.assertIn("Some prose", page)
        self.assertIn("A take-home", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<img", page)
        self.assertNotIn("http://", page)

    def test_programids(self):
        """Test that the programs of either pipeline are listed"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            build_example(data_dir)

            self.assertEqual(get_programids(NIGHT, data_dir), [1])

    def test_dead_quadrants_are_not_processed_by_both(self):
        """Test that a quadrant with no alerts at all is not counted as shared"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            build_example(data_dir)

            section = quadrant_section(NIGHT, data_dir)
            table = section.table["quadrants"]

            # one exposure of 64 quadrants, of which only rcid 8 holds alerts
            self.assertEqual(table.loc["quadrants in the night"], 64)
            self.assertEqual(table.loc["with alerts from both pipelines"], 1)
            self.assertEqual(table.loc["with no alerts from either pipeline"], 63)

    def test_agreement_is_colour_coded(self):
        """Test that a column's agreement carries a class the page can colour"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            build_example(data_dir)

            page = data_dir / "report.html"
            write_html_report(NIGHT, page, data_dir)

            self.assertIn('class="agree-', page.read_text())

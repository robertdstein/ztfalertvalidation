"""
Tests for reporting the result of each check
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from ztfalertvalidation import Section, build_summary, render_html, write_html_report

NIGHT = "20261112"

ALERTS = {
    "ipac": {
        "objectId": ["ZTF00a", "ZTF00b"],
        "jd": [1.0, 1.0],
        "rcid": [8, 8],
        "ra": [10.0, 10.1],
        "dec": [20.0, 20.0],
    },
    "dza": {
        "objectId": ["ZTF00x"],
        "jd": [1.0],
        "rcid": [8],
        "ra": [10.0],
        "dec": [20.0],
    },
}


def build_example(data_dir: Path) -> None:
    """
    Write a night of cached tables, and the avro files the volume check counts

    :param data_dir: Path to data directory
    :return: None
    """
    night_dir = data_dir / NIGHT
    alert_dirs = {"dza": night_dir / "dza", "ipac": night_dir / f"ztf_public_{NIGHT}"}

    for pipeline, values in ALERTS.items():
        alert_dirs[pipeline].mkdir(parents=True)
        for name in values["objectId"]:
            (alert_dirs[pipeline] / f"{name}.avro").write_bytes(b"x" * 1000)
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

            # the one DZA alert matches an IPAC one, and the other does not
            self.assertIn(NIGHT, page)
            self.assertIn("<table", page)

    def test_summary_collects_the_sections(self):
        """Test that the summary holds the night and each section's numbers"""
        sections = [
            Section("First", "", pd.DataFrame(), {"One": "1"}),
            Section("Second", "", pd.DataFrame(), {"Two": "2"}),
        ]

        summary = build_summary(sections, NIGHT)

        self.assertEqual(list(summary.index), ["Night", "One", "Two"])
        self.assertEqual(list(summary["value"]), [NIGHT, "1", "2"])

    def test_render_html_is_self_contained(self):
        """Test that the page needs nothing fetched to read it"""
        page = render_html([Section("Only", "Some prose", pd.DataFrame(), {})], NIGHT)

        self.assertIn("Some prose", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("<img", page)
        self.assertNotIn("http://", page)

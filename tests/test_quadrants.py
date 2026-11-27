"""
Tests for the quadrant comparison check
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from ztfalertvalidation import compare_quadrants, list_one_sided_quadrants
from ztfalertvalidation.checks.quadrants import N_QUADRANTS

NIGHT = "20261112"


def build_example(data_dir: Path) -> None:
    """
    Write a cached table for each pipeline

    :param data_dir: Path to data directory
    :return: None
    """
    night_dir = data_dir / NIGHT
    (night_dir / "dza").mkdir(parents=True)
    (night_dir / f"ztf_public_{NIGHT}").mkdir(parents=True)

    alerts = {
        "ipac": {"jd": [1.0, 1.0, 1.0], "rcid": [8, 8, 9]},
        "dza": {"jd": [1.0, 1.0, 2.0], "rcid": [8, 9, 8]},
    }
    for pipeline, values in alerts.items():
        pd.DataFrame(values).to_parquet(night_dir / f"{pipeline}.parquet")


class TestQuadrants(unittest.TestCase):
    """Tests for the quadrant comparison check"""

    def test_compare_quadrants(self):
        """Test that a quadrant absent from both pipelines counts NA"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            build_example(data_dir)

            df = compare_quadrants(NIGHT, data_dir)

            self.assertEqual(len(df), 2 * N_QUADRANTS)
            self.assertEqual(list(df.loc[(1.0, 8)]), [2, 1])
            self.assertEqual(list(df.loc[(2.0, 8)]), [0, 1])

            # quadrant 0 was read out by neither pipeline, in either exposure
            self.assertTrue(df.loc[(1.0, 0)].isna().all())
            self.assertTrue(df.loc[(2.0, 0)].isna().all())

    def test_list_one_sided_quadrants(self):
        """Test that only the quadrants one pipeline missed are listed"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            build_example(data_dir)

            df = list_one_sided_quadrants(NIGHT, data_dir)

            self.assertEqual(list(df.index), [(2.0, 8)])
            self.assertEqual(list(df.loc[(2.0, 8)]), [0, 1])

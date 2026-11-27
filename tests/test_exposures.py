"""
Tests for the exposure quadrant comparison check
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from ztfalertvalidation import compare_exposures

NIGHT = "20261112"


class TestExposures(unittest.TestCase):
    """Tests for the exposure quadrant comparison check"""

    def test_compare_exposures(self):
        """Test that the alerts of each quadrant are counted per pipeline"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            night_dir = data_dir / NIGHT
            (night_dir / "dza").mkdir(parents=True)
            (night_dir / f"ztf_public_{NIGHT}").mkdir(parents=True)

            # the checks read the cached tables, so the avros are not needed
            alerts = {
                "ipac": {"jd": [1.0, 1.0, 1.0], "rcid": [8, 8, 9]},
                "dza": {"jd": [1.0, 1.0, 2.0], "rcid": [8, 9, 8]},
            }
            for pipeline, values in alerts.items():
                pd.DataFrame(values).to_parquet(night_dir / f"{pipeline}.parquet")

            df = compare_exposures(NIGHT, data_dir)

            self.assertEqual(list(df.index), [(1.0, 8), (1.0, 9), (2.0, 8)])
            self.assertEqual(list(df["n_ipac"]), [2, 1, 0])
            self.assertEqual(list(df["n_dza"]), [1, 1, 1])

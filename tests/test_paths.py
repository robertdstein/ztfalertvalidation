"""
Tests for selecting alert directories
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ztfalertvalidation import get_dza_dir, get_ipac_dir, list_nights

NIGHT = "20261112"


class TestPaths(unittest.TestCase):
    """Tests for selecting alert directories"""

    def test_select_night(self):
        """Test that both pipeline directories of a night are found"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / NIGHT / "dza").mkdir(parents=True)
            (data_dir / NIGHT / f"ztf_public_{NIGHT}").mkdir(parents=True)

            self.assertEqual(list_nights(data_dir), [NIGHT])
            self.assertEqual(get_dza_dir(NIGHT, data_dir).name, "dza")
            self.assertEqual(get_ipac_dir(NIGHT, data_dir).name, f"ztf_public_{NIGHT}")

    def test_missing_night(self):
        """Test that an absent night raises, rather than returning a bad path"""
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                get_dza_dir(NIGHT, Path(temp_dir))

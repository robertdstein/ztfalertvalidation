"""
Tests for mapping the sources of the two pipelines onto each other
"""

import unittest

import pandas as pd

from ztfalertvalidation import add_nearest

ARCSEC = 1.0 / 3600.0

IPAC = pd.DataFrame(
    {
        "objectId": ["ZTF00a", "ZTF00b", "ZTF00c"],
        "jd": [1.0, 1.0, 2.0],
        "rcid": [8, 8, 8],
        "ra": [10.0, 10.1, 10.0],
        "dec": [20.0, 20.0, 20.0],
    }
)

DZA = pd.DataFrame(
    {
        "objectId": ["DZA00x", "DZA00y"],
        "jd": [1.0, 1.0],
        "rcid": [8, 8],
        "ra": [10.1, 10.0],
        "dec": [20.0, 20.0 + ARCSEC],
    }
)


class TestCrossmatch(unittest.TestCase):
    """Tests for mapping the sources of the two pipelines onto each other"""

    def test_add_nearest(self):
        """Test that each source is matched to its nearest counterpart"""
        df = add_nearest(IPAC, DZA, "DZAname", "DZAdist")

        self.assertEqual(list(df["DZAname"][:2]), ["DZA00y", "DZA00x"])
        self.assertAlmostEqual(df["DZAdist"].iloc[0], 1.0, places=6)
        self.assertAlmostEqual(df["DZAdist"].iloc[1], 0.0, places=6)

    def test_quadrant_without_match(self):
        """Test that a quadrant missing from the other table gets no match"""
        df = add_nearest(IPAC, DZA, "DZAname", "DZAdist")

        self.assertTrue(pd.isna(df["DZAname"].iloc[2]))
        self.assertTrue(pd.isna(df["DZAdist"].iloc[2]))

    def test_nearest_is_not_within_other_quadrants(self):
        """Test that a source is not matched across exposure quadrants"""
        other_quadrant = DZA.assign(rcid=9)
        df = add_nearest(IPAC, other_quadrant, "DZAname", "DZAdist")

        self.assertTrue(df["DZAname"].isna().all())

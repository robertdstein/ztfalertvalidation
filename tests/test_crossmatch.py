"""
Tests for mapping the sources of the two pipelines onto each other
"""

import unittest

import pandas as pd

from ztfalertvalidation import add_matches, match_tables

ARCSEC = 1.0 / 3600.0

IPAC = pd.DataFrame(
    {
        "objectId": ["ZTF00a", "ZTF00b", "ZTF00d", "ZTF00c"],
        "candid": [1, 2, 3, 4],
        "jd": [1.0, 1.0, 1.0, 2.0],
        "rcid": [8, 8, 8, 8],
        "ra": [10.0, 10.1, 10.2, 10.0],
        "dec": [20.0, 20.0, 20.0, 20.0],
    }
)

DZA = pd.DataFrame(
    {
        "objectId": ["DZA00x", "DZA00y"],
        "candid": [10, 20],
        "jd": [1.0, 1.0],
        "rcid": [8, 8],
        "ra": [10.1, 10.0],
        "dec": [20.0, 20.0 + 0.5 * ARCSEC],
    }
)


class TestCrossmatch(unittest.TestCase):
    """Tests for mapping the sources of the two pipelines onto each other"""

    def setUp(self):
        """Match the example tables"""
        matches = match_tables(IPAC, DZA)
        matched = add_matches(IPAC, DZA, matches, "DZA")
        self.df = matched.set_index("objectId")[["DZAname", "DZAid", "DZAdist"]]

    def test_nearest_within_the_cut(self):
        """Test that a source is matched to its nearest counterpart"""
        self.assertEqual(self.df["DZAname"].loc["ZTF00a"], "DZA00y")
        self.assertAlmostEqual(self.df["DZAdist"].loc["ZTF00a"], 0.5, places=6)

        self.assertEqual(self.df["DZAname"].loc["ZTF00b"], "DZA00x")
        self.assertAlmostEqual(self.df["DZAdist"].loc["ZTF00b"], 0.0, places=6)

    def test_nearest_beyond_the_cut(self):
        """Test that a counterpart further than the cut is not a match"""
        self.assertTrue(self.df.loc["ZTF00d"].isna().all())

    def test_quadrant_without_match(self):
        """Test that a quadrant missing from the other table gets no match"""
        self.assertTrue(self.df.loc["ZTF00c"].isna().all())

    def test_nearest_is_not_found_in_other_quadrants(self):
        """Test that a source is not matched across exposure quadrants"""
        other = DZA.assign(rcid=9)
        df = add_matches(IPAC, other, match_tables(IPAC, other), "DZA")

        self.assertTrue(df["DZAname"].isna().all())

    def test_matches_are_given_by_candid(self):
        """Test that a pair names the candid of each alert, not its position"""
        matches = match_tables(IPAC, DZA)

        self.assertEqual(list(matches["candid"]), [1, 2])
        self.assertEqual(list(matches["match_candid"]), [20, 10])

    def test_matched_id_is_exact(self):
        """Test that the matched candid survives, as a float would not"""
        candid = 3602476230915015004
        dza = DZA.assign(candid=[candid, 20])
        df = add_matches(IPAC, dza, match_tables(IPAC, dza), "DZA")

        self.assertEqual(df["DZAid"].dtype, "Int64")
        self.assertEqual(df.set_index("objectId")["DZAid"].loc["ZTF00b"], candid)
        self.assertTrue(pd.isna(df.set_index("objectId")["DZAid"].loc["ZTF00c"]))

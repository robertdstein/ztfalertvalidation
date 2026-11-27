"""
Tests for caching the alerts of a night as a table
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import fastavro
import pandas as pd

from ztfalertvalidation import get_dza_table, load_cached_table

SCHEMA = {
    "type": "record",
    "name": "alert",
    "fields": [
        {"name": "objectId", "type": "string"},
        {
            "name": "candidate",
            "type": {
                "type": "record",
                "name": "candidate",
                "fields": [{"name": "candid", "type": "long"}],
            },
        },
    ],
}

ALERT = {"objectId": "ZTF26abcdef", "candidate": {"candid": 3602476230915015004}}


class TestTables(unittest.TestCase):
    """Tests for caching the alerts of a night as a table"""

    def test_cache_is_reused(self):
        """Test that the table is cached, and read back from the cache"""
        with TemporaryDirectory() as temp_dir:
            alert_dir = Path(temp_dir)
            table_path = alert_dir / "alerts.parquet"

            with open(alert_dir / "alert.avro", "wb") as avro_f:
                fastavro.writer(avro_f, SCHEMA, [ALERT])

            df = load_cached_table(alert_dir, table_path)
            self.assertTrue(table_path.exists())

            (alert_dir / "alert.avro").unlink()
            cached = load_cached_table(alert_dir, table_path)

            self.assertTrue(cached.equals(df))

    def test_dza_sources_are_renamed(self):
        """Test that cached DZA alerts come back with a DZA name, not a ZTF one"""
        with TemporaryDirectory() as temp_dir:
            night = "20261112"
            night_dir = Path(temp_dir) / night
            (night_dir / "dza").mkdir(parents=True)

            table = pd.DataFrame({"objectId": ["ZTF26aaipcii"]})
            table.to_parquet(night_dir / "dza.parquet")

            df = get_dza_table(night, Path(temp_dir))

            self.assertEqual(list(df["objectId"]), ["DZA26aaipcii"])

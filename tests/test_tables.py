"""
Tests for caching the alerts of a night as a table
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import fastavro

from ztfalertvalidation import load_cached_table

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

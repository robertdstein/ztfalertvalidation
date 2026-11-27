"""
Tests for reading avro alerts
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import fastavro

from ztfalertvalidation import load_alerts

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
                "fields": [
                    {"name": "candid", "type": "long"},
                    {"name": "magpsf", "type": "float"},
                ],
            },
        },
        {"name": "cutoutScience", "type": "bytes"},
    ],
}

ALERT = {
    "objectId": "ZTF26abcdef",
    "candidate": {"candid": 3602476230915015004, "magpsf": 19.5},
    "cutoutScience": b"not-a-real-cutout",
}


class TestAvro(unittest.TestCase):
    """Tests for reading avro alerts"""

    def test_load_alerts(self):
        """Test that the candidate fields are flattened and the cutouts dropped"""
        with TemporaryDirectory() as temp_dir:
            alert_dir = Path(temp_dir)
            with open(alert_dir / "alert.avro", "wb") as avro_f:
                fastavro.writer(avro_f, SCHEMA, [ALERT])

            df = load_alerts(alert_dir)

            self.assertEqual(list(df.columns), ["objectId", "candid", "magpsf"])
            self.assertEqual(df["candid"].iloc[0], ALERT["candidate"]["candid"])

    def test_empty_dir(self):
        """Test that a directory with no alerts raises"""
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                load_alerts(Path(temp_dir))

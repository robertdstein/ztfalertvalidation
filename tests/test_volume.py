"""
Tests for the alert count and data volume check
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ztfalertvalidation import compare_volume

NIGHT = "20261112"


class TestVolume(unittest.TestCase):
    """Tests for the alert count and data volume check"""

    def test_compare_volume(self):
        """Test that each pipeline's alerts are counted and measured"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            dza = data_dir / NIGHT / "dza"
            ipac = data_dir / NIGHT / f"ztf_public_{NIGHT}"

            for alert_dir, n_alerts, n_bytes in [(dza, 3, 2000), (ipac, 2, 1000)]:
                alert_dir.mkdir(parents=True)
                for i in range(n_alerts):
                    (alert_dir / f"{i}.avro").write_bytes(b"x" * n_bytes)

            df = compare_volume(NIGHT, data_dir)

            self.assertEqual(list(df["n_alerts"]), [3, 2])
            self.assertEqual(list(df["volume_gb"]), [6e-6, 2e-6])
            self.assertEqual(list(df["mean_alert_kb"]), [2.0, 1.0])

"""
Tests for downloading the public alerts of a night
"""

import tarfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ztfalertvalidation import download_ipac_alerts, get_ipac_url, unpack_alerts

# a night with no public alerts, so its tarball is a few dozen bytes
EMPTY_NIGHT = "20261120"

# a night the archive does not hold, so downloading it would fail
MISSING_NIGHT = "19000101"


class TestDownload(unittest.TestCase):
    """Tests for downloading the public alerts of a night"""

    def test_bad_night(self):
        """Test that a night that is not a date is refused before any request"""
        for night in ["2026112", "20261112.tar.gz", "../etc", ""]:
            with self.subTest(night=night):
                with self.assertRaises(ValueError):
                    get_ipac_url(night)

    def test_unpack_alerts(self):
        """Test that the alerts of a tarball land in the directory"""
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            tarball = temp / "alerts.tar.gz"

            for name in ["1.avro", "2.avro"]:
                (temp / name).write_bytes(b"x")
            with tarfile.open(tarball, "w:gz") as tar:
                for name in ["1.avro", "2.avro"]:
                    tar.add(temp / name, arcname=name)

            alert_dir = temp / "alerts"
            unpack_alerts(tarball, alert_dir)

            self.assertEqual(
                sorted(x.name for x in alert_dir.glob("*.avro")), ["1.avro", "2.avro"]
            )

    def test_existing_alerts_are_not_downloaded(self):
        """Test that a night already on disk is left alone

        The night is one the archive does not hold, so a download would fail.
        """
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            alert_dir = data_dir / MISSING_NIGHT / f"ztf_public_{MISSING_NIGHT}"
            alert_dir.mkdir(parents=True)
            (alert_dir / "1.avro").write_bytes(b"x")

            self.assertEqual(download_ipac_alerts(MISSING_NIGHT, data_dir), alert_dir)

    def test_download_a_night(self):
        """Test downloading a real night, using one with no alerts in it"""
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)

            alert_dir = download_ipac_alerts(EMPTY_NIGHT, data_dir)

            self.assertTrue(alert_dir.is_dir())
            self.assertEqual(alert_dir.name, f"ztf_public_{EMPTY_NIGHT}")

            # the tarball is removed once it is unpacked
            self.assertEqual(list(alert_dir.parent.glob("*.tar.gz")), [])

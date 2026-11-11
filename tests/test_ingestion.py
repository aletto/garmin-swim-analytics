import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swim_analytics.cli import ingest
from swim_analytics.connectors.base import FitActivity
from swim_analytics.connectors.fit import LocalFitSource
from swim_analytics.connectors.garmin import load_garmin_source
from swim_analytics.storage import archive, preserve


class IngestionTests(unittest.TestCase):
    def test_reimport_preserves_one_blob_and_both_origins(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "invented.fit"
            payload = b"synthetic test payload"
            path.write_bytes(payload)
            with (
                patch("swim_analytics.cli.pool_message_counts", return_value={"length": 8}),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                ingest(LocalFitSource((path, path)), "local-fit", root)
            self.assertIn("Already archived", output.getvalue())

            with archive(root) as db:
                self.assertFalse(preserve(db, "garmin:mock", FitActivity(payload, "synthetic-01")))
                self.assertEqual(db.execute("SELECT fit FROM raw").fetchall(), [(payload,)])
                self.assertEqual(db.execute("SELECT count(*) FROM origins").fetchone(), (2,))

    def test_failed_validation_does_not_archive_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "bad.fit"
            path.write_bytes(b"invalid FIT")
            with patch("swim_analytics.cli.pool_message_counts", side_effect=ValueError):
                with self.assertRaises(ValueError):
                    ingest(LocalFitSource((path,)), "local-fit", root)
            with archive(root) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM raw").fetchone(), (0,))

    def test_garmin_adapter_is_explicit(self):
        with patch("swim_analytics.connectors.garmin.entry_points", return_value=[]) as points:
            with self.assertRaises(ValueError):
                load_garmin_source("missing")
            points.assert_called_once_with(group="swim_analytics.garmin", name="missing")

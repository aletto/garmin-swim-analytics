import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from garmin_fit_sdk import Encoder

from swim_analytics.cli import main
from swim_analytics.connectors.fit import pool_message_counts
from swim_analytics.storage import archive


def synthetic_fit(sub_sport=17):
    """Build a tiny invented FIT file in memory with no identifying metadata."""
    encoder = Encoder()
    encoder.write_mesg({"mesg_num": 0, "type": 4})  # Activity file
    for stroke, seconds in ((0, 24), (2, 34)):
        encoder.write_mesg({
            "mesg_num": 101,
            "length_type": 1,
            "swim_stroke": stroke,
            "total_timer_time": seconds,
        })
    encoder.write_mesg({
        "mesg_num": 18, "sport": 5, "sub_sport": sub_sport, "pool_length": 25
    })
    return bytes(encoder.close())


class FitTests(unittest.TestCase):
    def test_decodes_synthetic_pool_swim(self):
        self.assertEqual(
            pool_message_counts(synthetic_fit()),
            {"session": 1, "lap": 0, "length": 2, "record": 0},
        )

    def test_rejects_corrupt_and_open_water_files(self):
        with self.assertRaisesRegex(ValueError, "integrity"):
            pool_message_counts(synthetic_fit()[:-1])
        with self.assertRaisesRegex(ValueError, "No pool-swimming"):
            pool_message_counts(synthetic_fit(sub_sport=18))

    def test_import_command_archives_original_bytes_and_replays(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / "synthetic.fit"
            payload = synthetic_fit()
            file.write_bytes(payload)
            argv = ["swim-analytics", "--data-dir", str(root), "import-fit", str(file)]
            with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(), 0)
                self.assertEqual(main(), 0)
            self.assertIn("Imported (session=1, lap=0, length=2", output.getvalue())
            self.assertIn("Already archived", output.getvalue())
            with archive(root) as db:
                self.assertEqual(db.execute("SELECT fit FROM raw").fetchall(), [(payload,)])

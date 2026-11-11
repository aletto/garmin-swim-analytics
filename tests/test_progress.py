import contextlib
import io
import unittest

from garmin_fit_sdk import Encoder

from swim_analytics.connectors.fit import TimedLength
from swim_analytics.progress import _continuous_blocks, show_progress


class ProgressTests(unittest.TestCase):
    def test_quarantine_and_swolf_coverage_are_stroke_specific(self):
        encoder = Encoder()
        encoder.write_mesg({"mesg_num": 0, "type": 4})
        times = (22, 23, 23, 24, 24, 25, 25, 26, 65)
        for index, seconds in enumerate(times):
            encoder.write_mesg({
                "mesg_num": 101, "message_index": index,
                "length_type": 1, "swim_stroke": 0,
                "total_timer_time": seconds, "total_strokes": 12,
            })
        encoder.write_mesg({
            "mesg_num": 101, "message_index": len(times),
            "length_type": 1, "swim_stroke": 2, "total_timer_time": 42,
        })
        encoder.write_mesg({"mesg_num": 19, "first_length_index": 0, "num_lengths": len(times) + 1})
        encoder.write_mesg({
            "mesg_num": 18, "sport": 5, "sub_sport": 17, "pool_length": 25,
            "start_time": 1100000000,
        })
        payload = bytes(encoder.close())

        with contextlib.redirect_stdout(io.StringIO()) as clean:
            show_progress([payload], 25)
        with contextlib.redirect_stdout(io.StringIO()) as raw:
            show_progress([payload], 25, raw=True)

        self.assertRegex(clean.getvalue(), r"Freestyle\s+\S+\s+24.0\s+36.0\s+8\s+8\s+1")
        self.assertRegex(raw.getvalue(), r"Freestyle\s+\S+\s+24.0\s+36.0\s+9\s+9\s+1")
        self.assertRegex(clean.getvalue(), r"Breaststroke\s+\S+\s+42.0\s+—\s+1\s+0\s+0")

    def test_blocks_require_consecutive_same_stroke_lengths_in_one_interval(self):
        observations = [
            (TimedLength(stroke, seconds, 12, interval, index), flagged)
            for index, stroke, interval, seconds, flagged in [
                (0, "freestyle", 0, 30, False),
                (1, "freestyle", 0, 30, False),
                (3, "freestyle", 0, 30, False),
                (4, "breaststroke", 0, 40, False),
                (5, "freestyle", 1, 29, False),
                (6, "freestyle", 1, 31, False),
                (7, "freestyle", 1, 30, False),
                (8, "freestyle", 1, 60, True),
                (9, "freestyle", 2, 30, False),
            ]
        ]
        self.assertEqual(list(_continuous_blocks(observations, 4)), [("freestyle", 150, True)])

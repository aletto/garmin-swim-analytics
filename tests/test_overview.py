import contextlib
import io
import unittest

from garmin_fit_sdk import Encoder

from swim_analytics.overview import show_overview


class OverviewTests(unittest.TestCase):
    def test_separates_rests_strokes_and_pool_sizes(self):
        payloads = []
        for pool_m in (25, 50):
            encoder = Encoder()
            encoder.write_mesg({"mesg_num": 0, "type": 4})
            for length_type, stroke, duration in ((1, 0, 25), (1, 2, 40), (0, 0, 200)):
                encoder.write_mesg({
                    "mesg_num": 101,
                    "length_type": length_type,
                    "swim_stroke": stroke,
                    "total_timer_time": duration,
                })
            encoder.write_mesg({
                "mesg_num": 18, "sport": 5, "sub_sport": 17,
                "pool_length": pool_m, "total_distance": 2 * pool_m,
            })
            payloads.append(bytes(encoder.close()))

        with contextlib.redirect_stdout(io.StringIO()) as output:
            show_overview(payloads)
        overview = output.getvalue()
        self.assertIn("Sessions: 2", overview)
        self.assertIn("Active lengths: 4", overview)
        self.assertIn("Rest records: 2", overview)
        self.assertRegex(overview, r"Freestyle\s+25m\s+1\s+1:40\s+1:40")
        self.assertRegex(overview, r"Breaststroke\s+25m\s+1\s+2:40\s+2:40")
        self.assertRegex(overview, r"Freestyle\s+50m\s+1\s+0:50\s+0:50")

import json
import unittest
from pathlib import Path

from swim_analytics.quality import Length, Status, assess

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic" / "lengths.json"


class QualityTests(unittest.TestCase):
    def setUp(self):
        groups = json.loads(FIXTURE.read_text())
        self.reference = [
            Length(stroke, 25, context, seconds)
            for group, durations in groups.items()
            if group != "description"
            for stroke, context in [group.split("_", maxsplit=1)]
            for seconds in durations
        ]

    def test_paces_are_compared_only_within_stroke_and_context(self):
        for stroke, context, seconds in [
            ("freestyle", "main", 24),
            ("breaststroke", "main", 34),
            ("freestyle", "recovery", 40),
            ("freestyle", "sprint", 17),
        ]:
            with self.subTest(stroke=stroke, context=context):
                result = assess(Length(stroke, 25, context, seconds), self.reference)
                self.assertEqual(result.status, Status.VALID)
                self.assertEqual(result.sample_count, 8)

    def test_both_fast_and_slow_outliers_are_quarantined_without_changing_length(self):
        for seconds in (10, 50):
            observed = Length("freestyle", 25, "main", seconds)
            result = assess(observed, self.reference)
            self.assertEqual(result.status, Status.QUARANTINED)
            self.assertEqual(observed.pool_m, 25)
            self.assertEqual(observed.timer_s, seconds)

    def test_sparse_and_constant_reference(self):
        observed = Length("freestyle", 25, "main", 50)
        self.assertEqual(assess(observed, []).reason, "insufficient_reference")
        constant = [Length("freestyle", 25, "main", 24)] * 8
        result = assess(observed, constant)
        self.assertEqual(result.status, Status.SUSPECT)
        self.assertIsNone(result.score)

    def test_pool_size_and_unknown_stroke_are_handled_separately(self):
        self.assertEqual(assess(Length("freestyle", 50, "main", 50), self.reference).sample_count, 0)
        self.assertEqual(assess(Length("drill", 25, "main", 50), self.reference).score, None)

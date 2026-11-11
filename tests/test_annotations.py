import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from garmin_fit_sdk import Encoder

from swim_analytics.annotations import (
    AnnotationError,
    confirmed_workouts,
    parse_block,
    parse_garmin_note,
    save_annotation,
    show_session,
)
from swim_analytics.connectors.base import FitActivity
from swim_analytics.connectors.fit import RecordedInterval, RecordedWorkout
from swim_analytics.storage import archive, archived_payloads, preserve


class AnnotationTests(unittest.TestCase):
    def test_local_mapping_overrides_only_distance_matched_laps(self):
        encoder = Encoder()
        encoder.write_mesg({"mesg_num": 0, "type": 4})
        for index in range(4):
            encoder.write_mesg({
                "mesg_num": 101, "message_index": index, "length_type": 1,
                "swim_stroke": 0, "total_timer_time": 36, "total_strokes": 12,
            })
        for first in (0, 2):
            encoder.write_mesg({"mesg_num": 19, "first_length_index": first, "num_lengths": 2})
        encoder.write_mesg({
            "mesg_num": 18, "sport": 5, "sub_sport": 17, "pool_length": 25,
            "start_time": 1100000000,
        })
        payload = bytes(encoder.close())

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with archive(root) as db:
                preserve(db, "garmin:personal", FitActivity(payload, "42"))
            self.assertEqual(list(confirmed_workouts(root)), [])

            with contextlib.redirect_stdout(io.StringIO()) as output:
                save_annotation(root, "42", [parse_block("1:crol:50")], "First pass")
                save_annotation(
                    root, "42", [parse_block("1:pecho:50"), parse_block("2:crol:25")], "Reviewed"
                )
                save_annotation(
                    root, "42", [parse_block("1:pecho:50"), parse_block("2:crol:25")], "Reviewed"
                )
                show_session(root, "42")
                with self.assertRaisesRegex(AnnotationError, "overlap"):
                    save_annotation(
                        root, "42", [parse_block("1-2:pecho:100"), parse_block("2:crol:50")], ""
                    )
            self.assertIn("Excluded from confirmed length metrics", output.getvalue())
            self.assertIn("Note: Reviewed", output.getvalue())
            self.assertRegex(output.getvalue(), r"\b1\s+2\s+50\s+freestyle=2")
            workout, = confirmed_workouts(root)
            self.assertEqual([length.stroke for length in workout.timed_lengths], ["breaststroke"] * 2)
            self.assertEqual(list(archived_payloads(root)), [payload])
            with archive(root) as db:
                notes = db.execute("SELECT note FROM stroke_annotations ORDER BY revision").fetchall()
            self.assertEqual(notes, [("First pass",), ("Reviewed",)])

    def test_parses_only_one_explicit_garmin_mapping_line(self):
        blocks, note = parse_garmin_note(
            "Unrelated note\r\n SWIM: 3-5:crol:300, 7:pecho:200\r\nMore free text"
        )
        self.assertEqual(blocks, [parse_block("3-5:crol:300"), parse_block("7:pecho:200")])
        self.assertEqual(note, "SWIM: 3-5:crol:300, 7:pecho:200")
        with self.assertRaisesRegex(AnnotationError, "exactly one"):
            parse_garmin_note("SWIM: 3:crol:25\nSWIM: 5:pecho:25")
        with self.assertRaises(AnnotationError):
            parse_garmin_note("SWIM: 3:crol:25,")

    def test_aligns_ordered_strokes_without_using_detected_styles(self):
        intervals = tuple(
            RecordedInterval(lap, count, (("freestyle", count),))
            for lap, count in [(1, 2), (3, 2), (5, 5), (7, 4)]
        )
        workout = RecordedWorkout(None, 325, 25, 13, 0, (), intervals)
        blocks, _ = parse_garmin_note("SWIM: 50 crol, 50m crol, 100 pecho, 100 crol", workout)
        self.assertEqual(blocks, [
            parse_block("1-3:crol:100"), parse_block("5:pecho:100"), parse_block("7:crol:100"),
        ])

    def test_rejects_tied_ordered_alignments(self):
        intervals = tuple(RecordedInterval(i, n, ()) for i, n in [(1, 2), (3, 1), (5, 2)])
        workout = RecordedWorkout(None, 125, 25, 5, 0, (), intervals)
        with self.assertRaisesRegex(AnnotationError, "multiple interval mappings"):
            parse_garmin_note("SWIM: 50 crol, 50 pecho", workout)
        with self.assertRaisesRegex(AnnotationError, "do not fit"):
            parse_garmin_note("SWIM: 50 crol, 200 pecho", workout)

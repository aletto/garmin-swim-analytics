import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import asdict, dataclass
from itertools import accumulate
from math import isclose
from pathlib import Path

from .connectors.fit import RecordedWorkout, read_recorded_workout
from .storage import archive

STROKES = {
    "crol": "freestyle",
    "freestyle": "freestyle",
    "pecho": "breaststroke",
    "breaststroke": "breaststroke",
}


class AnnotationError(ValueError):
    """A session mapping could not be resolved safely."""


@dataclass(frozen=True)
class Block:
    first: int
    last: int
    stroke: str
    meters: int

    @property
    def laps(self) -> range:
        return range(self.first, self.last + 1)


def parse_block(value: str) -> Block:
    lap_span, sep, remainder = value.partition(":")
    stroke, next_sep, distance = remainder.partition(":")
    start, _, end = lap_span.partition("-")
    try:
        first, last, meters = int(start), int(end or start), int(distance)
        normalized = STROKES[stroke.strip().lower()]
    except (ValueError, KeyError):
        raise AnnotationError("Use --block LAP[-LAP]:crol|pecho:METERS.") from None
    if not sep or not next_sep or not 1 <= first <= last or meters <= 0:
        raise AnnotationError("Use a valid lap range and a positive block distance.")
    return Block(first, last, normalized, meters)


@dataclass(frozen=True)
class Alignment:
    error: int
    blocks: tuple[Block, ...]
    ambiguous: bool = False


def _ordered_blocks(items: list[str], workout: RecordedWorkout) -> list[Block]:
    pool_m = workout.pool_m
    if pool_m is None:
        raise AnnotationError("The FIT has no usable pool size.")
    requested: list[tuple[int, str]] = []
    for item in items:
        match = re.fullmatch(r"([0-9]+)\s*(?:m\s*)?([a-z]+)", item.strip().lower())
        if not match or match[2] not in STROKES or int(match[1]) <= 0:
            raise AnnotationError("Use ordered distances and strokes, for example SWIM: 100 crol, 50 pecho.")
        meters, stroke = int(match[1]), STROKES[match[2]]
        expected = round(meters / pool_m)
        if expected < 1 or not isclose(expected * pool_m, meters, abs_tol=0.01):
            raise AnnotationError("Ordered distances must be multiples of the pool length.")
        if requested and requested[-1][1] == stroke:
            previous, _ = requested.pop()
            meters += previous
        requested.append((meters, stroke))

    laps = workout.intervals
    prefix = list(accumulate((lap.active_lengths for lap in laps), initial=0))
    if prefix[-1] != workout.active_count:
        raise AnnotationError("Some active lengths have no FIT interval. Use explicit lap numbers.")
    boundary_at = {lengths: index for index, lengths in enumerate(prefix)}
    states = {0: Alignment(0, ())}
    for meters, stroke in requested:
        expected = round(meters / pool_m)
        next_states: dict[int, Alignment] = {}
        for start, alignment in states.items():
            for difference in (0, -1, 1):
                end = boundary_at.get(prefix[start] + expected + difference)
                if end is None or end <= start:
                    continue
                error = alignment.error + abs(difference)
                best = next_states.get(end)
                if best is None or error < best.error:
                    block = Block(laps[start].number, laps[end - 1].number, stroke, meters)
                    next_states[end] = Alignment(error, (*alignment.blocks, block), alignment.ambiguous)
                elif error == best.error:
                    next_states[end] = Alignment(error, best.blocks, ambiguous=True)
        states = next_states

    result = states.get(len(laps))
    if result is None:
        raise AnnotationError("The ordered distances do not fit the recorded intervals. Use explicit lap numbers.")
    if result.ambiguous:
        raise AnnotationError("The ordered note matches multiple interval mappings. Use explicit lap numbers.")
    return list(result.blocks)


def parse_garmin_note(
    description: str, workout: RecordedWorkout | None = None
) -> tuple[list[Block], str]:
    lines = [
        line.strip() for line in description.splitlines()
        if line.strip().startswith("SWIM:")
    ]
    if len(lines) != 1:
        raise AnnotationError("The Garmin note must contain exactly one SWIM: mapping line.")
    line = lines[0]
    content = line.removeprefix("SWIM:")
    items = content.split(",")
    if ":" in content:
        return [parse_block(item.strip()) for item in items], line
    if workout is None:
        raise AnnotationError("An archived FIT is required to map an ordered note.")
    return _ordered_blocks(items, workout), line


def _session(db: sqlite3.Connection, activity_id: str) -> tuple[str, bytes]:
    rows = db.execute(
        """SELECT DISTINCT raw.digest, raw.fit FROM raw JOIN origins USING (digest)
           WHERE origins.source LIKE 'garmin:%' AND origins.external_id = ?
           LIMIT 2""",
        (activity_id,),
    ).fetchall()
    if len(rows) != 1:
        raise AnnotationError("Expected one archived FIT version for this Garmin activity ID.")
    digest, payload = rows[0]
    return str(digest), bytes(payload)


def _overrides(
    workout: RecordedWorkout, blocks: list[Block]
) -> tuple[dict[int, str], list[tuple[Block, float]]]:
    if workout.pool_m is None:
        raise AnnotationError("The FIT has no usable pool size.")
    active = {lap.number: lap.active_lengths for lap in workout.intervals}
    used: set[int] = set()
    overrides: dict[int, str] = {}
    mismatches = []
    for block in blocks:
        if block.first not in active or block.last not in active:
            raise AnnotationError("The first and last lap of each block must contain active lengths.")
        if used.intersection(block.laps):
            raise AnnotationError("Blocks must not overlap.")
        used.update(block.laps)
        distance = sum(active.get(lap, 0) for lap in block.laps) * workout.pool_m
        if not isclose(distance, block.meters, abs_tol=0.01):
            mismatches.append((block, distance))
            continue
        overrides.update((lap, block.stroke) for lap in block.laps)
    return overrides, mismatches


def _latest_annotation(db: sqlite3.Connection, digest: str) -> tuple[str, str] | None:
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stroke_annotations'"
    ).fetchone() is None:
        return None
    row = db.execute(
        "SELECT blocks, note FROM stroke_annotations WHERE digest = ? ORDER BY revision DESC LIMIT 1",
        (digest,),
    ).fetchone()
    return (str(row[0]), str(row[1])) if row is not None else None


def show_session(root: Path, activity_id: str) -> None:
    with archive(root) as db:
        digest, payload = _session(db, activity_id)
        annotation = _latest_annotation(db, digest)
    workout = read_recorded_workout(payload)
    print("FIT lap    Active lengths    Meters    Garmin stroke labels")
    for lap in workout.intervals:
        labels = ", ".join(f"{stroke}={count}" for stroke, count in lap.detected_strokes)
        meters = f"{lap.active_lengths * workout.pool_m:g}" if workout.pool_m is not None else "—"
        print(f"{lap.number:>7} {lap.active_lengths:>17} {meters:>9}    {labels}")
    if annotation is not None:
        encoded, note = annotation
        print("\nLatest manual mapping:")
        for item in json.loads(encoded):
            block = Block(**item)
            print(f"  FIT laps {block.first}–{block.last}: {block.stroke}, {block.meters} m")
        if note:
            print(f"Note: {note}")


def save_annotation(root: Path, activity_id: str, blocks: list[Block] | None, note: str) -> None:
    """Save explicit blocks, or resolve a Garmin description against the archived FIT."""
    from_garmin = blocks is None
    with archive(root) as db:
        digest, payload = _session(db, activity_id)
        workout = read_recorded_workout(payload)
        if blocks is None:
            blocks, note = parse_garmin_note(note, workout)
        _, mismatches = _overrides(workout, blocks)
        db.execute("""
            CREATE TABLE IF NOT EXISTS stroke_annotations (
                revision INTEGER PRIMARY KEY,
                digest TEXT NOT NULL REFERENCES raw(digest),
                blocks TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        encoded = json.dumps([asdict(block) for block in blocks])
        if _latest_annotation(db, digest) == (encoded, note):
            print("This annotation is already saved.")
            return
        db.execute(
            "INSERT INTO stroke_annotations(digest, blocks, note) VALUES (?, ?, ?)",
            (digest, encoded, note),
        )
    print(f"Saved a local annotation for {len(blocks)} blocks.")
    if from_garmin:
        for block in blocks:
            print(f"FIT laps {block.first}–{block.last}: {block.meters} m {block.stroke}.")
    for block, distance in mismatches:
        print(
            f"FIT laps {block.first}–{block.last}: annotated {block.meters} m, "
            f"recorded {distance:g} m. Excluded from confirmed length metrics."
        )


def confirmed_workouts(root: Path) -> Iterator[RecordedWorkout]:
    path = root / "raw.sqlite3"
    if not path.is_file():
        return
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stroke_annotations'"
        ).fetchone() is None:
            return
        for payload, encoded in db.execute("""
            SELECT raw.fit, a.blocks FROM stroke_annotations AS a JOIN raw USING (digest)
            WHERE a.revision = (
                SELECT MAX(b.revision) FROM stroke_annotations AS b WHERE b.digest = a.digest
            )
        """):
            blocks = [Block(**block) for block in json.loads(encoded)]
            workout = read_recorded_workout(payload)
            overrides, _ = _overrides(workout, blocks)
            yield read_recorded_workout(payload, overrides)

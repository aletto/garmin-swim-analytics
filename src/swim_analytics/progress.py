from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from itertools import groupby
from statistics import median

from .connectors.fit import RecordedWorkout, TimedLength, read_recorded_workout
from .quality import Length, Status, assess


def _assess_intervals(
    lengths: tuple[TimedLength, ...], pool_m: float
) -> Iterator[tuple[TimedLength, bool]]:
    intervals: dict[tuple[int | None, str], list[TimedLength]] = defaultdict(list)
    for length in lengths:
        intervals[length.interval, length.stroke].append(length)

    for (interval, stroke), group in intervals.items():
        if interval is None:
            for length in group:
                yield length, False
            continue

        peers = [Length(stroke, pool_m, "recorded interval", item.seconds) for item in group]
        for index, item in enumerate(group):
            reference = peers[:index] + peers[index + 1:]
            result = assess(peers[index], reference)
            yield item, result.status == Status.QUARANTINED


def _median(values: list[float]) -> str:
    return f"{median(values):.1f}" if values else "—"


def _recorded_workouts(payloads: Iterable[bytes]) -> Iterator[RecordedWorkout]:
    skipped = 0
    for payload in payloads:
        try:
            workout = read_recorded_workout(payload)
        except ValueError:
            skipped += 1
            continue
        yield workout
    if skipped:
        print(f"FIT files skipped (invalid or unsupported): {skipped}")


def show_progress(
    payloads: Iterable[bytes], pool_m: float, *, raw: bool = False,
    confirmed: Iterable[RecordedWorkout] | None = None,
) -> None:
    groups: dict[tuple[str, str], list[TimedLength]] = defaultdict(list)
    flags: dict[tuple[str, str], int] = defaultdict(int)
    workouts = _recorded_workouts(payloads) if confirmed is None else confirmed
    for workout in workouts:
        if workout.pool_m != pool_m or workout.started_at is None:
            continue

        month = workout.started_at.strftime("%Y-%m")
        for length, flagged in _assess_intervals(workout.timed_lengths, pool_m):
            key = length.stroke, month
            flags[key] += flagged
            if raw or not flagged:
                groups[key].append(length)

    if not flags:
        print(f"No dated freestyle or breaststroke lengths in a {pool_m:g} m pool.")
        return

    mode = "raw" if raw else "excluding quarantined lengths"
    source = "Garmin-detected styles" if confirmed is None else "manually confirmed styles"
    print(f"Monthly swim progress · {pool_m:g} m · {source} · {mode}")
    print("Stroke         Month      Median s/length  Median SWOLF  Lengths  SWOLF n  Flagged")
    for (stroke, month), flagged_count in sorted(flags.items()):
        lengths = groups[stroke, month]
        swolf = [item.seconds + item.strokes for item in lengths if item.strokes is not None]
        print(
            f"{stroke.capitalize():<14} {month} "
            f"{_median([item.seconds for item in lengths]):>15} {_median(swolf):>13} "
            f"{len(lengths):>8} {len(swolf):>8} {flagged_count:>8}"
        )


def _continuous_blocks(
    assessed: Iterable[tuple[TimedLength, bool]], block_size: int
) -> Iterator[tuple[str, float, bool]]:
    indexed = [
        (item.index, item, flagged) for item, flagged in assessed
        if item.interval is not None and item.index is not None
    ]
    indexed.sort(key=lambda row: row[0])
    for _, run in groupby(
        enumerate(indexed),
        key=lambda row: (row[1][1].interval, row[1][1].stroke, row[1][0] - row[0]),
    ):
        lengths = [row for _, row in run]
        for start in range(0, len(lengths) - block_size + 1, block_size):
            block = lengths[start:start + block_size]
            yield block[0][1].stroke, sum(row.seconds for _, row, _ in block), any(
                flagged for _, _, flagged in block
            )


def show_continuous_progress(
    payloads: Iterable[bytes], pool_m: float, block_size: int, *, raw: bool = False,
    confirmed: Iterable[RecordedWorkout] | None = None,
) -> None:
    observed: list[tuple[date, str, float, bool]] = []
    workouts = _recorded_workouts(payloads) if confirmed is None else confirmed
    for workout in workouts:
        if workout.pool_m != pool_m or workout.started_at is None:
            continue
        observed.extend(
            (workout.started_at.date(), stroke, seconds, flagged)
            for stroke, seconds, flagged in _continuous_blocks(
                _assess_intervals(workout.timed_lengths, pool_m), block_size
            )
        )

    distance = pool_m * block_size
    mode = "raw" if raw else "excluding blocks with quarantined lengths"
    source = "Garmin-detected styles" if confirmed is None else "manually confirmed styles"
    print(f"{distance:g} m continuous blocks · {pool_m:g} m pool · {source} · {mode}")
    print("Stroke         Period           Median s/100m   Blocks  Flagged")
    today = date.today()
    recent_start = today - timedelta(days=29)
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    flags: dict[tuple[str, str], int] = defaultdict(int)
    for day, stroke, seconds, flagged in observed:
        periods = [day.strftime("%Y-%m")]
        if recent_start <= day <= today:
            periods.append("Last 30 days")
        for period in periods:
            key = stroke, period
            flags[key] += flagged
            if raw or not flagged:
                groups[key].append(seconds * 100 / distance)
    for stroke in ("breaststroke", "freestyle"):
        flags.setdefault((stroke, "Last 30 days"), 0)
    for (stroke, period), count in sorted(flags.items()):
        paces = groups[stroke, period]
        print(
            f"{stroke.capitalize():<14} {period:<16} {_median(paces):>13} "
            f"{len(paces):>8} {count:>8}"
        )

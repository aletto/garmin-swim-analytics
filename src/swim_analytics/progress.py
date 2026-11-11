from collections import defaultdict
from collections.abc import Iterable, Iterator
from statistics import median

from .connectors.fit import TimedLength, read_recorded_workout
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


def show_progress(payloads: Iterable[bytes], pool_m: float, *, raw: bool = False) -> None:
    groups: dict[tuple[str, str], list[TimedLength]] = defaultdict(list)
    flags: dict[tuple[str, str], int] = defaultdict(int)
    skipped = 0
    for payload in payloads:
        try:
            workout = read_recorded_workout(payload)
        except ValueError:
            skipped += 1
            continue
        if workout.pool_m != pool_m or workout.started_at is None:
            continue

        month = workout.started_at.strftime("%Y-%m")
        for length, flagged in _assess_intervals(workout.timed_lengths, pool_m):
            key = length.stroke, month
            flags[key] += flagged
            if raw or not flagged:
                groups[key].append(length)

    if skipped:
        print(f"FIT files skipped (invalid or unsupported): {skipped}")
    if not flags:
        print(f"No dated freestyle or breaststroke lengths in a {pool_m:g} m pool.")
        return

    mode = "raw" if raw else "excluding quarantined lengths"
    print(f"Monthly swim progress · {pool_m:g} m · {mode}")
    print("Stroke         Month      Median s/length  Median SWOLF  Lengths  SWOLF n  Flagged")
    for (stroke, month), flagged_count in sorted(flags.items()):
        lengths = groups[stroke, month]
        swolf = [item.seconds + item.strokes for item in lengths if item.strokes is not None]
        print(
            f"{stroke.capitalize():<14} {month} "
            f"{_median([item.seconds for item in lengths]):>15} {_median(swolf):>13} "
            f"{len(lengths):>8} {len(swolf):>8} {flagged_count:>8}"
        )

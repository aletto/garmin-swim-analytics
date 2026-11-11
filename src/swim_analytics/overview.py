from collections import defaultdict
from collections.abc import Iterable
from statistics import median

from .connectors.fit import read_recorded_workout


def _pace(seconds: float) -> str:
    minutes, seconds_rounded = divmod(round(seconds), 60)
    return f"{minutes}:{seconds_rounded:02d}"


def show_overview(payloads: Iterable[bytes]) -> None:
    workouts = []
    skipped = 0
    for payload in payloads:
        try:
            workouts.append(read_recorded_workout(payload))
        except ValueError:
            skipped += 1

    if skipped:
        print(f"FIT files skipped (invalid or unsupported): {skipped}")
    if not workouts:
        print("No pool workouts to show. Run sync-garmin or import-fit first.")
        return

    print("Pool swimming overview (raw observations)")
    print(f"Sessions: {len(workouts)}")
    distances = [row.reported_m for row in workouts if row.reported_m is not None]
    if distances:
        print(f"Garmin-reported distance: {sum(distances) / 1000:.2f} km ({len(distances)} sessions)")
    print(f"Active lengths: {sum(row.active_count for row in workouts)}")
    print(f"Rest records: {sum(row.rest_count for row in workouts)}")

    paces: dict[tuple[str, float], list[float]] = defaultdict(list)
    volume: dict[str, list[float | None]] = defaultdict(list)
    for row in workouts:
        month = row.started_at.strftime("%Y-%m") if row.started_at else "Unknown date"
        volume[month].append(row.reported_m)
        if row.pool_m is not None:
            for length in row.timed_lengths:
                paces[length.stroke.capitalize(), row.pool_m].append(100 * length.seconds / row.pool_m)

    print("\nStroke          Pool    Lengths    Mean /100m   Median /100m")
    for (stroke, pool_m), values in sorted(paces.items()):
        print(
            f"{stroke:<14} {pool_m:>5g}m {len(values):>8} "
            f"{_pace(sum(values) / len(values)):>12} {_pace(median(values)):>14}"
        )
    if not paces:
        print("No timed freestyle or breaststroke lengths with a known pool size.")

    print("\nMonth (FIT)    Sessions    Garmin distance")
    for month, monthly in sorted(volume.items()):
        known = [value for value in monthly if value is not None]
        distance = f"{sum(known) / 1000:.2f} km ({len(known)} with distance)" if known else "unavailable"
        print(f"{month:<14} {len(monthly):>7}    {distance}")

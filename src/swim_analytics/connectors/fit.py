from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING

from .base import FitActivity

if TYPE_CHECKING:
    from garmin_fit_sdk.mesgs import FitMessages


@dataclass(frozen=True)
class LocalFitSource:
    paths: tuple[Path, ...]

    def activities(self) -> Iterable[FitActivity]:
        for path in self.paths:
            yield FitActivity(path.read_bytes())


def _decode_pool(payload: bytes) -> FitMessages:
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError as exc:
        raise RuntimeError("Install the FIT extra with pip install '.[fit]'.") from exc

    stream = Stream.from_byte_array(bytearray(payload))
    decoder = Decoder(stream)
    if not decoder.check_integrity():
        raise ValueError("FIT integrity check failed.")
    stream.reset()
    messages, errors = decoder.read(convert_types_to_strings=False)
    if errors:
        raise ValueError("FIT decoding reported errors.")
    # FIT profile enum values for swimming and lap swimming.
    if not any(
        row.get("sport") == 5 and row.get("sub_sport") == 17
        for row in messages.get("session_mesgs", ())
    ):
        raise ValueError("No pool-swimming session found in the FIT file.")
    return messages


def pool_message_counts(payload: bytes) -> dict[str, int]:
    """Validate the file and inventory its pool-swim messages without exposing values."""
    messages = _decode_pool(payload)
    return {
        "session": len(messages.get("session_mesgs", ())),
        "lap": len(messages.get("lap_mesgs", ())),
        "length": len(messages.get("length_mesgs", ())),
        "record": len(messages.get("record_mesgs", ())),
    }


@dataclass(frozen=True)
class TimedLength:
    stroke: str
    seconds: float
    strokes: int | None
    interval: int | None


@dataclass(frozen=True)
class RecordedWorkout:
    started_at: datetime | None
    reported_m: float | None
    pool_m: float | None
    active_count: int
    rest_count: int
    timed_lengths: tuple[TimedLength, ...]


def read_recorded_workout(payload: bytes) -> RecordedWorkout:
    """Read a single pool session without guessing length membership across sessions."""
    messages = _decode_pool(payload)
    sessions = messages.get("session_mesgs", [])
    if len(sessions) != 1:
        raise ValueError("The overview requires one session per FIT file.")

    session = sessions[0]
    lengths = messages.get("length_mesgs", [])
    active = [row for row in lengths if row.get("length_type") == 1]
    intervals: dict[int, int | None] = {}
    for interval, lap in enumerate(messages.get("lap_mesgs", [])):
        first = lap.get("first_length_index")
        count = lap.get("num_lengths")
        if first is not None and count is not None:
            for index in range(first, first + count):
                intervals[index] = interval if index not in intervals else None

    timed = []
    strokes = {0: "freestyle", 2: "breaststroke"}
    for row in active:
        stroke_code = row.get("swim_stroke")
        stroke = strokes.get(stroke_code) if isinstance(stroke_code, int) else None
        seconds = row.get("total_timer_time")
        if stroke is not None and seconds is not None and isfinite(seconds) and seconds > 0:
            count = row.get("total_strokes")
            length_index = row.get("message_index")
            timed.append(TimedLength(
                stroke,
                seconds,
                count if count is not None and count > 0 else None,
                intervals.get(length_index) if isinstance(length_index, int) else None,
            ))

    started_at = session.get("start_time")
    pool_m = session.get("pool_length")  # FIT profile always encodes this in meters.
    reported_m = session.get("total_distance")
    return RecordedWorkout(
        started_at if isinstance(started_at, datetime) else None,
        reported_m if reported_m is not None and isfinite(reported_m) and reported_m >= 0 else None,
        pool_m if pool_m is not None and isfinite(pool_m) and pool_m > 0 else None,
        len(active),
        sum(row.get("length_type") == 0 for row in lengths),
        tuple(timed),
    )

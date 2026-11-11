from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from statistics import median


class Status(StrEnum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    QUARANTINED = "QUARANTINED"
    MANUALLY_CORRECTED = "MANUALLY_CORRECTED"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class Length:
    stroke: str
    pool_m: float
    context: str
    timer_s: float

    @property
    def group(self) -> tuple[str, float, str]:
        return self.stroke, self.pool_m, self.context


@dataclass(frozen=True)
class Rules:
    min_samples: int = 8
    suspect_z: float = 2.5
    quarantine_z: float = 3.5

    def __post_init__(self) -> None:
        if self.min_samples < 3 or not 0 < self.suspect_z < self.quarantine_z < float("inf"):
            raise ValueError("Expected at least three samples and ordered finite thresholds.")


@dataclass(frozen=True)
class Assessment:
    status: Status
    reason: str
    score: float | None = None
    sample_count: int = 0


def assess(
    target: Length, reference: Iterable[Length], rules: Rules = Rules()
) -> Assessment:
    """Assess one length against caller-selected historical or workout-local peers.

    The caller supplies a trusted reference set that excludes the target.
    A quarantine status is a review decision, never proof of a device error.
    """
    if target.stroke not in {"freestyle", "breaststroke"}:
        return Assessment(Status.VALID, "outside_supported_stroke_baseline")
    if not all(isfinite(v) and v > 0 for v in (target.pool_m, target.timer_s)):
        return Assessment(Status.QUARANTINED, "invalid_distance_or_timer")
    values = [
        row.timer_s for row in reference
        if row.group == target.group and isfinite(row.timer_s) and row.timer_s > 0
    ]
    count = len(values)
    if count < rules.min_samples:
        return Assessment(Status.VALID, "insufficient_reference", sample_count=count)
    center = median(values)
    mad = median(abs(value - center) for value in values)
    if mad == 0:
        status = Status.VALID if target.timer_s == center else Status.SUSPECT
        return Assessment(status, "zero_reference_mad", sample_count=count)
    score = 0.6745 * (target.timer_s - center) / mad
    status = Status.VALID
    if abs(score) > rules.quarantine_z:
        status = Status.QUARANTINED
    elif abs(score) > rules.suspect_z:
        status = Status.SUSPECT
    return Assessment(status, "stroke_context_mad", score, count)

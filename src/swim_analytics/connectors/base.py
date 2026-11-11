from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FitActivity:
    """Original FIT bytes plus the provider's activity identifier, if known."""

    payload: bytes
    external_id: str | None = None


class ActivitySource(Protocol):
    """An adapter yields original FIT payloads without touching local storage."""

    def activities(self) -> Iterable[FitActivity]: ...

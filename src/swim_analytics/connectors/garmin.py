from importlib.metadata import entry_points
from typing import cast

from .base import ActivitySource

GROUP = "swim_analytics.garmin"


def load_garmin_source(name: str) -> ActivitySource:
    """Load one explicitly selected, locally installed connector factory."""
    matches = entry_points(group=GROUP, name=name)
    if len(matches) != 1:
        raise ValueError("Install a Garmin connector with a unique matching entry point.")
    return cast(ActivitySource, matches[0].load()())

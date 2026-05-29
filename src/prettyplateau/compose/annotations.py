"""Annotation helpers — non-data figure overlays.

Examples include scale bars, event-year tick marks, and decorative
divider strokes. Currently consumed by `survivor_timeline` (event-year
strip) and re-exposed here for community presets.
"""

from __future__ import annotations

from prettyplateau.presets.scene import TextAnnotation


def event_strip(*, year: int, year_lo: int, year_hi: int, label: str, color: str, is_current: bool) -> TextAnnotation:
    """Build the annotation for a single event-year tick mark on the timeline strip."""
    span = max(year_hi - year_lo, 1)
    x = 0.06 + (year - year_lo) / span * 0.88
    return TextAnnotation(
        text=label,
        x=x,
        y=0.155,
        align="left",
        valign="bottom",
        color=color,
        size=7.0,
        weight="medium" if is_current else "regular",
        z=9_500,
    )

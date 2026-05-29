"""Layout math — figure-fraction reservations for title / legend / attribution.

The composer's `CompositionOptions.top_margin()` etc. already compute these,
but the plan-shaped package surface puts the math in its own module so a
third-party composer (e.g. a poster-grid composer) can call the same
functions without depending on `CompositionOptions`.
"""

from __future__ import annotations


def top_margin_for(title: str | None, subtitle: str | None) -> float:
    if title and subtitle:
        return 0.07
    if title or subtitle:
        return 0.05
    return 0.015


def bottom_margin_for(show_legend: bool, legend_position: str) -> float:
    m = 0.02  # attribution + breathing room
    if show_legend and legend_position == "bottom":
        m += 0.10
    return m


def side_margin_for(show_legend: bool, legend_position: str) -> float:
    if show_legend and legend_position == "right":
        return 0.20
    return 0.015

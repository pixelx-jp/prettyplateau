"""Caption rendering for animation presets.

The plan distinguishes captions ("用于解释「现存建筑时间线」等语义风险")
from attribution. Captions can be hidden by the user; attribution cannot.
This module hosts the helper that turns a `TimelineSpec.caption` into a
matplotlib text overlay during animator setup.
"""

from __future__ import annotations

from matplotlib.figure import Figure


def overlay_caption(figure: Figure, caption: str | None, *, color: str = "#666666") -> None:
    """Draw the timeline caption beneath the legend band.

    Returns silently when caption is None — many static-export paths bypass
    this entirely. Position is fixed in figure-fraction coordinates so the
    composer's margin reservations stay in sync.
    """
    if not caption:
        return
    figure.text(
        0.5,
        0.012,
        caption,
        color=color,
        fontsize=7.5,
        ha="center",
        va="bottom",
        zorder=9_200,
        wrap=True,
    )

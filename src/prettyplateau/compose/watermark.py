"""Watermark module — placeholder for non-attribution decorative marks.

`attribution_injector.py` owns the mandatory CC BY 4.0 line. This module
is reserved for *user-supplied* watermarks (logos, edition numbers). It's
intentionally minimal in v1: the plan defers user logos and the rule is
that any user watermark must NOT cover the mandatory attribution.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatermarkSpec:
    """Future surface for user-supplied watermarks.

    `text` is the visible string; `corner` chooses placement. The composer
    will refuse `corner` placements that would collide with the mandatory
    attribution corner (`AttributionStyle.corner`).
    """

    text: str
    corner: str = "top-right"
    size_pt: float = 8.0


def collides_with_attribution(watermark: WatermarkSpec, attribution_corner: str) -> bool:
    """True when a user watermark would overlap the attribution corner."""
    return watermark.corner == attribution_corner

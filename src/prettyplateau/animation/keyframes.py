"""Keyframe helpers for building TimelineSpecs.

Currently a small toolbox preset authors can lean on instead of hand-rolling
linspace-and-zip code. As more animation presets land we expect this module
to grow — keep it free of any single preset's quirks.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def evenly_spaced_years(
    year_lo: int,
    year_hi: int,
    n_frames: int,
) -> list[int]:
    """Return n_frames integer years spanning [year_lo, year_hi] inclusive."""
    if n_frames <= 0:
        return []
    if n_frames == 1:
        return [int(year_lo)]
    return [int(y) for y in np.linspace(year_lo, year_hi, n_frames)]


def normalise_t(values: Iterable[float]) -> list[float]:
    """Rescale a sequence of monotonic values into [0, 1]."""
    items = list(values)
    if not items:
        return []
    lo, hi = float(min(items)), float(max(items))
    if hi - lo <= 0:
        return [0.0] * len(items)
    return [(v - lo) / (hi - lo) for v in items]

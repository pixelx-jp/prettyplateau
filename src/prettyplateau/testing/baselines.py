"""Baseline-file helpers used by the visual regression suite.

The bulk of regression logic lives in `tests/visual/test_baselines.py`
(where pytest expects it). This module exposes the small pure helpers
that don't depend on pytest so plugins / CI scripts can call them.
"""

from __future__ import annotations

from pathlib import Path

from prettyplateau.testing.image_diff import perceptual_hash, rms_diff


def compare_to_baseline(current: Path, baseline: Path) -> tuple[float, int]:
    """Return (rms, dhash_distance) between current render and baseline.

    rms is in [0,1]; dhash distance is the Hamming distance between the
    16x16 dHashes. Callers decide the pass thresholds.
    """
    rms = rms_diff(current, baseline)
    cur_hash = perceptual_hash(current)
    base_hash = perceptual_hash(baseline)
    distance = sum(a != b for a, b in zip(cur_hash, base_hash, strict=False))
    return rms, distance

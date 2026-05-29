"""Hazard helpers — turn raw plateau-bridge fields into a renderable model.

The key invariant: `covered=false` means *no data*, never *low risk*. A preset
that paints `covered=false` as "safe" is buggy. Everything in this module
exists to make that invariant easy to honour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from prettyplateau.data.schema import (
    HAZARD_DEPTH_KINDS,
    HAZARD_KINDS,
    hazard_covered_col,
    hazard_depth_col,
    hazard_in_zone_col,
)

HazardKind = Literal["river_flood", "inland_flood", "tsunami", "storm_surge", "landslide"]

# River-flood / inundation depth buckets, metres.
DEPTH_BUCKETS: tuple[tuple[float, float, str], ...] = (
    (-1.0, 0.5, "lt_05"),
    (0.5, 1.0, "05_1"),
    (1.0, 3.0, "1_3"),
    (3.0, 5.0, "3_5"),
    (5.0, 10.0, "5_10"),
    (10.0, float("inf"), "ge_10"),
)


@dataclass(frozen=True)
class HazardSummary:
    """Coverage summary for a single hazard kind."""

    kind: str
    n_total: int
    n_covered: int
    n_hit: int

    @property
    def coverage_ratio(self) -> float:
        return self.n_covered / self.n_total if self.n_total else 0.0


def summarise(df: pd.DataFrame) -> dict[str, HazardSummary]:
    """Per-hazard coverage summary; useful for warnings/legends."""
    out: dict[str, HazardSummary] = {}
    n_total = len(df)
    for kind in HAZARD_KINDS:
        covered_col = hazard_covered_col(kind)
        if covered_col not in df.columns:
            out[kind] = HazardSummary(kind=kind, n_total=n_total, n_covered=0, n_hit=0)
            continue
        covered = df[covered_col].fillna(False).astype(bool)
        if kind in HAZARD_DEPTH_KINDS:
            depth = df.get(hazard_depth_col(kind))
            hit = covered & (pd.to_numeric(depth, errors="coerce") > 0) if depth is not None else covered
        else:
            zone = df.get(hazard_in_zone_col(kind))
            hit = covered & (zone.fillna(False).astype(bool)) if zone is not None else covered
        out[kind] = HazardSummary(
            kind=kind,
            n_total=n_total,
            n_covered=int(covered.sum()),
            n_hit=int(hit.sum()),
        )
    return out


def depth_bucket(values: pd.Series) -> pd.Series:
    """Classify depth-max values into bucket keys, leaving NaN -> 'no_data'."""
    nums = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float, copy=False)
    out = np.empty(nums.shape[0], dtype=object)
    out[:] = "no_data"
    isna = np.isnan(nums)
    for lo, hi, key in DEPTH_BUCKETS:
        mask = (~isna) & (nums >= lo) & (nums < hi) & (nums > 0)
        out[mask] = key
    # depth <= 0 with covered=true counts as covered-but-not-hit; preset decides.
    zero_mask = (~isna) & (nums <= 0)
    out[zero_mask] = "lt_05"
    return pd.Series(out, index=values.index, name="depth_bucket")


def assign_river_flood_keys(df: pd.DataFrame) -> pd.Series:
    """Return a Series mapping each building to a `risk_depth` palette key.

    Rule:
      covered=False                  -> 'no_data'
      covered=True, depth >  0       -> bucket
      covered=True, depth missing/<=0 -> 'lt_05' (covered but not in inundation)
    """
    covered = df[hazard_covered_col("river_flood")].fillna(False).astype(bool)
    depth = df.get(hazard_depth_col("river_flood"))
    keys = depth_bucket(depth) if depth is not None else pd.Series(["no_data"] * len(df), index=df.index)
    keys = keys.where(covered, other="no_data")
    return keys.rename("river_flood_key")

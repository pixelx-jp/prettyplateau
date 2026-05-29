"""Helpers shared across built-in presets."""

from __future__ import annotations

import numpy as np
import pandas as pd  # noqa: F401  (used by bbox_of_gdf)

# Standard age bucket bounds (year built). Inclusive-exclusive on the lower bound.
AGE_BUCKETS: tuple[tuple[int, int, str, str], ...] = (
    (1850, 1925, "pre_1925", "pre-1925"),
    (1925, 1946, "1925_1945", "1925–1945"),
    (1946, 1971, "1946_1970", "1946–1970"),
    (1971, 1981, "1971_1980", "1971–1980 (pre-shin-taishin)"),
    (1981, 2001, "1981_2000", "1981–2000 (shin-taishin)"),
    (2001, 2011, "2001_2010", "2001–2010"),
    (2011, 9999, "2011_present", "2011–present"),
)

# Plateau-bridge sometimes emits `year_built = 1` as a sentinel for "unknown
# but present in upstream data". Anything below this floor is treated as
# unknown so a sentinel-poisoned dataset doesn't show up as "100% pre-1925".
_YEAR_FLOOR = 1850


def assign_age_keys(years: pd.Series) -> pd.Series:
    """Bucket year-built values; NaN or year < 1850 → 'unknown'."""
    nums = pd.to_numeric(years, errors="coerce").to_numpy(dtype=float, copy=False)
    out = np.full(nums.shape[0], "unknown", dtype=object)
    not_na = (~np.isnan(nums)) & (nums >= _YEAR_FLOOR)
    for lo, hi, key, _label in AGE_BUCKETS:
        out[not_na & (nums >= lo) & (nums < hi)] = key
    return pd.Series(out, index=years.index, name="age_key")


def bbox_of_gdf(gdf, *, percentile: float = 0.999) -> tuple[float, float, float, float]:
    """Return a robust lon/lat bounding box.

    PLATEAU outputs sometimes contain a handful of outlier polygons at the very
    edge of the prefecture (overflow from adjacent administrative areas). Using
    `total_bounds` directly lets those outliers push the canvas wide and squish
    the actual city to a corner. We clip the bounds to a (1-p)..p centroid
    percentile, which keeps the city centred without losing useful coverage.
    """
    if gdf.empty:
        return (0.0, 0.0, 0.0, 0.0)
    if "centroid_lon" in gdf.columns and "centroid_lat" in gdf.columns:
        lon = pd.to_numeric(gdf["centroid_lon"], errors="coerce").dropna()
        lat = pd.to_numeric(gdf["centroid_lat"], errors="coerce").dropna()
        if not lon.empty and not lat.empty:
            lo = 1.0 - percentile
            return (
                float(lon.quantile(lo)),
                float(lat.quantile(lo)),
                float(lon.quantile(percentile)),
                float(lat.quantile(percentile)),
            )
    try:
        minx, miny, maxx, maxy = gdf.total_bounds
        if any(np.isnan([minx, miny, maxx, maxy])):
            raise ValueError("total_bounds had NaN")
        return float(minx), float(miny), float(maxx), float(maxy)
    except Exception:  # noqa: BLE001
        return (0.0, 0.0, 0.0, 0.0)

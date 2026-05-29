"""Lightweight building filters used by presets.

All filters return a *new* GeoDataFrame; nothing mutates the input.
"""

from __future__ import annotations

from typing import Iterable

import geopandas as gpd
import pandas as pd

from prettyplateau.data.schema import (
    COL_STRUCTURE,
    COL_USAGE,
    COL_YEAR_BUILT,
)


def filter_bbox(gdf: gpd.GeoDataFrame, bbox: tuple[float, float, float, float] | None) -> gpd.GeoDataFrame:
    if bbox is None:
        return gdf
    minx, miny, maxx, maxy = bbox
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    return gdf.cx[minx:maxx, miny:maxy]


def filter_year_range(
    gdf: gpd.GeoDataFrame,
    lo: int | None = None,
    hi: int | None = None,
    include_unknown: bool = True,
) -> gpd.GeoDataFrame:
    if COL_YEAR_BUILT not in gdf.columns:
        return gdf if include_unknown else gdf.iloc[0:0]
    years = pd.to_numeric(gdf[COL_YEAR_BUILT], errors="coerce")
    mask = pd.Series(False, index=gdf.index)
    if lo is None and hi is None:
        mask = years.notna()
    else:
        mask = years.notna()
        if lo is not None:
            mask &= years >= lo
        if hi is not None:
            mask &= years <= hi
    if include_unknown:
        mask |= years.isna()
    return gdf[mask]


# plateau-bridge canonicalises Structure to {wood, rc, steel, src, other}.
# We accept both the canonical token and Japanese-source synonyms so older
# datasets and citizen-side parquets still classify correctly.
WOOD_STRUCTURE_TOKENS: tuple[str, ...] = ("wood", "木造", "木", "Wood", "WOOD")


def filter_wood(gdf: gpd.GeoDataFrame, tokens: Iterable[str] = WOOD_STRUCTURE_TOKENS) -> gpd.GeoDataFrame:
    if COL_STRUCTURE not in gdf.columns:
        return gdf.iloc[0:0]
    s = gdf[COL_STRUCTURE].astype("string").fillna("")
    mask = pd.Series(False, index=gdf.index)
    for t in tokens:
        mask |= s.str.contains(t, case=False, na=False)
    return gdf[mask]


def filter_usage(gdf: gpd.GeoDataFrame, usages: Iterable[str]) -> gpd.GeoDataFrame:
    if COL_USAGE not in gdf.columns:
        return gdf.iloc[0:0]
    keep = set(usages)
    return gdf[gdf[COL_USAGE].astype("string").isin(keep)]

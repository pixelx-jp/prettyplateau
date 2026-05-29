"""Embedded minimal subset of plateau-bridge.

This module exists only so Week 1-2 of prettyplateau doesn't block on plateau-core's
public API. It implements the smallest possible read path:

  - locate `out_<city>/buildings.parquet` + `manifest.json`
  - materialise a GeoDataFrame in EPSG:4326
  - surface `attribution`, `dataset_id`, and `field_coverage`

Everything else is out of scope. From Week 4 the default `DataAccess` adapter
switches to importing `plateau_bridge` directly and this module becomes a
fixture / offline fallback.

DO NOT import this module from preset code. Always go through `data.access`.
"""

from prettyplateau._core_lite.attribution import read_attribution
from prettyplateau._core_lite.filters import (
    WOOD_STRUCTURE_TOKENS,
    filter_bbox,
    filter_usage,
    filter_wood,
    filter_year_range,
)
from prettyplateau._core_lite.loader import (
    CITY_ALIASES,
    LiteCityDataset,
    LiteManifest,
    discover_city,
    load_buildings,
    load_manifest,
)

__all__ = [
    "CITY_ALIASES",
    "LiteCityDataset",
    "LiteManifest",
    "discover_city",
    "load_buildings",
    "load_manifest",
    "read_attribution",
    "filter_bbox",
    "filter_year_range",
    "filter_wood",
    "filter_usage",
    "WOOD_STRUCTURE_TOKENS",
]

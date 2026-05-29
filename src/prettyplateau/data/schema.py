"""Canonical column names from plateau-bridge's `buildings.parquet`.

Keeping this in one place lets every preset depend on a single source of truth.
If plateau-core renames a column, only this file changes.
"""

from __future__ import annotations

# Core building fields.
COL_GEOMETRY = "geometry"
COL_BUILDING_UID = "building_uid"
COL_CITY_CODE = "city_code"
COL_USAGE = "usage"
COL_YEAR_BUILT = "year_built"
COL_STRUCTURE = "structure"
COL_FIRE_RESISTANCE = "fire_resistance"
COL_HEIGHT = "height"
COL_FLOORS_ABOVE = "floors_above"
COL_FLOORS_BELOW = "floors_below"
COL_CENTROID_LON = "centroid_lon"
COL_CENTROID_LAT = "centroid_lat"
COL_DATASET_YEAR = "dataset_year"
COL_SOURCE_DATASET_ID = "source_dataset_id"
COL_ATTRIBUTION = "attribution"
COL_ZONING_USE = "zoning_use"
COL_FAR_MAX = "far_max"

# Hazard fields use the `{kind}_{suffix}` pattern.
HAZARD_KINDS: tuple[str, ...] = (
    "river_flood",
    "inland_flood",
    "tsunami",
    "storm_surge",
    "landslide",
)
HAZARD_DEPTH_KINDS: tuple[str, ...] = (
    "river_flood",
    "inland_flood",
    "tsunami",
    "storm_surge",
)


def hazard_covered_col(kind: str) -> str:
    return f"{kind}_covered"


def hazard_coverage_confidence_col(kind: str) -> str:
    return f"{kind}_coverage_confidence"


def hazard_depth_col(kind: str) -> str:
    return f"{kind}_depth_max"


def hazard_in_zone_col(kind: str) -> str:
    return f"{kind}_in_zone"

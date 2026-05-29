"""Plan-mandated hazard `covered=false` test.

The plan explicitly requires: "hazard 测试必须覆盖 covered=false. 测试断言
no-data 不会进入 low-risk bucket." This guards against a regression where
a downstream change might pipe `covered=false` through the depth bucketer
and end up colouring it as "lt_05" (the lowest *real* risk bucket).
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from prettyplateau.data.hazard import assign_river_flood_keys
from prettyplateau.data.schema import (
    hazard_covered_col,
    hazard_depth_col,
)


def _make_gdf(rows: list[tuple[bool, float | None]]) -> gpd.GeoDataFrame:
    """Build a GeoDataFrame from (covered, depth_max) tuples."""
    polys = [Polygon([(i, 0), (i + 1, 0), (i + 1, 1), (i, 1)]) for i in range(len(rows))]
    return gpd.GeoDataFrame(
        {
            hazard_covered_col("river_flood"): [r[0] for r in rows],
            hazard_depth_col("river_flood"): [r[1] for r in rows],
        },
        geometry=polys,
        crs="EPSG:4326",
    )


def test_covered_false_is_no_data_regardless_of_depth() -> None:
    # A building that's outside the dataset's coverage must be `no_data` even
    # if the (stale) depth value would have classified as 'lt_05'. This is
    # the load-bearing invariant of the entire risk family.
    gdf = _make_gdf([
        (False, None),
        (False, 0.0),
        (False, 0.2),    # would be 'lt_05' if naively bucketed
        (False, 7.5),    # would be '5_10' if naively bucketed
    ])
    keys = assign_river_flood_keys(gdf)
    assert list(keys) == ["no_data"] * 4


def test_covered_true_buckets_correctly() -> None:
    gdf = _make_gdf([
        (True, 0.2),     # < 0.5 m
        (True, 0.7),     # 0.5–1
        (True, 1.5),     # 1–3
        (True, 3.5),     # 3–5
        (True, 7.5),     # 5–10
        (True, 12.0),    # ≥ 10
        (True, None),    # covered but no depth value
    ])
    keys = assign_river_flood_keys(gdf)
    assert keys.tolist() == ["lt_05", "05_1", "1_3", "3_5", "5_10", "ge_10", "no_data"]

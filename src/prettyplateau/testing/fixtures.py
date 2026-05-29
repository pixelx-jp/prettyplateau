"""Synthetic fixture data for fast unit/visual tests.

We *don't* commit a real PLATEAU parquet to the repo (license + size). Instead,
each test builds a small synthetic GeoDataFrame in-memory; the only thing tested
end-to-end against real PLATEAU data is the gallery smoke render, run manually.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from prettyplateau.data.access import CityDataset


def make_fixture_buildings(n: int = 200, *, seed: int = 0) -> gpd.GeoDataFrame:
    """A grid of unit-square buildings with deterministic attributes."""
    rng = np.random.default_rng(seed)
    side = int(np.ceil(np.sqrt(n)))
    polys: list[Polygon] = []
    years: list[float] = []
    structures: list[str] = []
    usages: list[str] = []
    heights: list[float] = []
    for i in range(n):
        r = i // side
        c = i % side
        x0 = 139.7 + c * 0.0005
        y0 = 35.65 + r * 0.0005
        polys.append(Polygon([(x0, y0), (x0 + 0.0004, y0), (x0 + 0.0004, y0 + 0.0004), (x0, y0 + 0.0004)]))
        years.append(float(rng.choice([1920, 1955, 1975, 1990, 2005, 2020, np.nan])))
        structures.append(rng.choice(["wood", "rc", "steel", "other", None]))
        usages.append(rng.choice(["residential", "commercial", "educational", "industrial", "public"]))
        heights.append(float(rng.uniform(3, 60)))
    zoning_choices = ['["第1種住居地域"]', '["商業地域"]', '["近隣商業地域"]', '["工業地域"]', None]
    gdf = gpd.GeoDataFrame(
        {
            "year_built": years,
            "structure": structures,
            "usage": usages,
            "height": heights,
            "fire_resistance": ["耐火"] * n,
            "centroid_lon": [p.centroid.x for p in polys],
            "centroid_lat": [p.centroid.y for p in polys],
            "river_flood_covered": rng.choice([True, False], n),
            "river_flood_depth_max": rng.choice([0.2, 1.5, 3.0, np.nan], n),
            "landslide_covered": rng.choice([True, False], n),
            "landslide_in_zone": rng.choice([True, False], n),
            "zoning_use": [zoning_choices[i % len(zoning_choices)] for i in range(n)],
        },
        geometry=polys,
        crs="EPSG:4326",
    )
    return gdf


def fixture_dataset(n: int = 200) -> CityDataset:
    gdf = make_fixture_buildings(n)
    return CityDataset(
        city="fixture",
        city_name="Fixture City",
        city_code="00000",
        dataset_year=2024,
        dataset_id="fixture-dataset-2024",
        attribution="© Project PLATEAU / MLIT (CC BY 4.0)",
        field_coverage={"year_built": 0.85, "structure": 0.8, "usage": 1.0, "height": 1.0},
        n_buildings=len(gdf),
        gdf=gdf,
    )

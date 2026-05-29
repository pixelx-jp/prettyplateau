"""Hazard Confluence — count of overlapping hazard categories per building.

Plan: highlight zones where multiple PLATEAU hazard layers stack (river +
landslide, river + tsunami, etc.). The preset counts the number of hazards
each building is hit by, with 0 / 1 / 2 / 3+ buckets. Buildings with no
hazard coverage at all are rendered as `no_data` (hashed grey) — never as
"zero hazards" — to respect the same invariant `risk_choropleth` enforces.
"""

from __future__ import annotations

import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.schema import (
    HAZARD_DEPTH_KINDS,
    HAZARD_KINDS,
    hazard_covered_col,
    hazard_depth_col,
    hazard_in_zone_col,
)
from prettyplateau.presets._common import bbox_of_gdf
from prettyplateau.presets._layers import admin_boundary_layer
from prettyplateau.presets.base import BasePreset, PreparedData
from prettyplateau.presets.scene import (
    LegendEntry,
    LegendSpec,
    PolygonLayer,
    RenderScene,
)
from prettyplateau.style.palette import apply_theme_overrides, load_palette
from prettyplateau.style.theme import Theme


class HazardConfluencePreset(BasePreset):
    metadata = PresetMetadata(
        id="hazard_confluence",
        name="Hazard Confluence",
        description="Per-building count of overlapping PLATEAU hazard categories.",
        modes=["static"],
        required_fields=[hazard_covered_col("river_flood")],
        optional_fields=[hazard_covered_col(k) for k in HAZARD_KINDS if k != "river_flood"],
        required_hazards=["river_flood"],
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        n = len(gdf)
        any_covered = pd.Series(False, index=gdf.index)
        hit_count = pd.Series(0, index=gdf.index)

        for kind in HAZARD_KINDS:
            ccol = hazard_covered_col(kind)
            if ccol not in gdf.columns:
                continue
            covered = gdf[ccol].fillna(False).astype(bool)
            any_covered |= covered
            if kind in HAZARD_DEPTH_KINDS:
                depth = pd.to_numeric(gdf.get(hazard_depth_col(kind)), errors="coerce")
                hit = covered & depth.fillna(0).gt(0)
            else:
                zone = gdf.get(hazard_in_zone_col(kind))
                if zone is None:
                    hit = pd.Series(False, index=gdf.index)
                else:
                    hit = covered & zone.fillna(False).astype(bool)
            hit_count = hit_count + hit.astype(int)

        keys = pd.Series(["no_data"] * n, index=gdf.index, dtype="object")
        keys[any_covered & (hit_count == 0)] = "zero"
        keys[hit_count == 1] = "one"
        keys[hit_count == 2] = "two"
        keys[hit_count >= 3] = "three_plus"

        n_no_data = int((keys == "no_data").sum())
        warnings: tuple[str, ...] = ()
        if n_no_data == n:
            warnings = (f"no hazard coverage at all for {dataset.city!r}; output will be entirely no-data.",)
        elif n_no_data > 0.5 * n:
            warnings = (f"{n_no_data}/{n} buildings have no hazard coverage; hashed grey dominates.",)
        return PreparedData(
            dataset=dataset,
            derived={"confluence_keys": keys, "n_three_plus": int((keys == "three_plus").sum())},
            warnings=warnings,
        )

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys = prepared.derived["confluence_keys"]
        palette = apply_theme_overrides(load_palette("hazard_confluence"), theme)
        key_list = keys.tolist()
        fills = [palette.color_for(k) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,

            fill_keys=key_list,
            z=10,
            semantic={"field": "hazard_confluence"},
        )
        entries = (
            LegendEntry(label="0 hazards hit", color=palette.color_for("zero")),
            LegendEntry(label="1 hazard", color=palette.color_for("one")),
            LegendEntry(label="2 hazards", color=palette.color_for("two")),
            LegendEntry(label="3+ hazards", color=palette.color_for("three_plus")),
            LegendEntry(label="No hazard data", color=palette.color_for("no_data"), is_no_data=True),
        )
        legend = LegendSpec(
            title="Hazard confluence",
            entries=entries,
            note="A building is counted in a hazard if its PLATEAU coverage is non-null AND it is inside the hazard polygon.",
        )
        boundary = admin_boundary_layer(ds, theme)
        layers = (boundary, layer) if boundary else (layer,)
        return RenderScene(
            bounds=bbox_of_gdf(gdf),
            background=theme.background,
            layers=layers,
            legend=legend,
            semantic_metadata={
                "preset": self.metadata.id,
                "n_buildings": int(len(gdf)),
                "n_three_plus": prepared.derived.get("n_three_plus", 0),
            },
        )


PRESET = HazardConfluencePreset()


def factory() -> HazardConfluencePreset:
    return HazardConfluencePreset()

"""Flood Depth — per-building river-flood depth bucket.

Where the plan's flagship `risk_choropleth` requires wood × era × flood and
falls back to no-data when era is missing, this preset asks the simpler
question: *just paint each building by its flood depth bucket*. It's the
right preset when structure / year_built are unavailable but you still want
to communicate hazard exposure honestly.

The critical invariant is identical to `risk_choropleth`: buildings with
`river_flood_covered=False` are **no-data**, never "low risk".
"""

from __future__ import annotations

import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.hazard import assign_river_flood_keys
from prettyplateau.data.schema import (
    COL_STRUCTURE,
    COL_YEAR_BUILT,
    hazard_covered_col,
    hazard_depth_col,
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

_DEPTH_LABELS: dict[str, str] = {
    "lt_05": "< 0.5 m",
    "05_1": "0.5–1 m",
    "1_3": "1–3 m",
    "3_5": "3–5 m",
    "5_10": "5–10 m",
    "ge_10": "≥ 10 m",
    "no_data": "No data",
}


class FloodDepthPreset(BasePreset):
    metadata = PresetMetadata(
        id="flood_depth",
        name="Flood Depth",
        description="Per-building river-flood depth bucket. No-data is hashed grey, never recoloured as safe.",
        modes=["static"],
        required_fields=[hazard_covered_col("river_flood"), hazard_depth_col("river_flood")],
        optional_fields=[COL_STRUCTURE, COL_YEAR_BUILT],
        required_hazards=["river_flood"],
        default_format="png",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        depth_keys = assign_river_flood_keys(gdf)

        covered_total = int(gdf[hazard_covered_col("river_flood")].fillna(False).astype(bool).sum())
        warnings: list[str] = []
        if covered_total == 0:
            warnings.append(
                f"city {dataset.city!r} has no river_flood coverage; every building will be no-data."
            )
        elif covered_total / max(len(gdf), 1) < 0.3:
            warnings.append(
                f"only {covered_total/len(gdf):.0%} of buildings are within river_flood coverage; "
                "the rest are hashed as no-data."
            )

        derived = {
            "depth_keys": depth_keys,
            "n_covered": covered_total,
            "n_no_data": int((depth_keys == "no_data").sum()),
            "n_hit": int(((depth_keys != "no_data") & (depth_keys != "lt_05")).sum()),
        }
        return PreparedData(dataset=dataset, derived=derived, warnings=tuple(warnings))

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys: pd.Series = prepared.derived["depth_keys"]
        palette = apply_theme_overrides(load_palette("flood_depth"), theme)
        key_list = keys.tolist()
        fills = [palette.color_for(k) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,

            fill_keys=key_list,
            z=10,
            semantic={"field": "river_flood_depth_max"},
        )

        entries = tuple(
            LegendEntry(label=_DEPTH_LABELS[k], color=palette.color_for(k))
            for k in ("lt_05", "05_1", "1_3", "3_5", "5_10", "ge_10")
        ) + (
            LegendEntry(
                label=_DEPTH_LABELS["no_data"],
                color=palette.color_for("no_data"),
                is_no_data=True,
            ),
        )
        legend = LegendSpec(
            title="River flood — maximum depth",
            entries=entries,
            note="Hashed grey = no PLATEAU river-flood coverage for this building (NOT 'low risk').",
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
                "n_covered": prepared.derived["n_covered"],
                "n_no_data": prepared.derived["n_no_data"],
                "n_hit": prepared.derived["n_hit"],
            },
        )


PRESET = FloodDepthPreset()


def factory() -> FloodDepthPreset:
    return FloodDepthPreset()

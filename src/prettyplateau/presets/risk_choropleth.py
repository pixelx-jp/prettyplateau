"""Risk Choropleth — pre-1981 wood × river-flood depth (plan-defined flagship).

The plan's "Risk Choropleth" is the *compound* preset: intersect per-building
era (pre-1981 vs post-shin-taishin), structure (wood vs other), and PLATEAU's
river-flood depth band. PLATEAU is the only public dataset that exposes those
three per building, so this preset is the textbook differentiator.

The simpler "every building coloured by flood depth alone" view lives under
`flood_depth` for cases where era / structure data is missing.

Coverage caveat: this preset needs `structure` (real wood values, not
collapsed `other`) and `year_built`. Tokyo wards currently have neither — on
those datasets the preset dominates with the `no_data` swatch. That's the
truthful output, not a bug.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.filters import WOOD_STRUCTURE_TOKENS
from prettyplateau.data.hazard import assign_river_flood_keys
from prettyplateau.data.schema import (
    COL_FIRE_RESISTANCE,
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

_WOOD_FIRE_TOKENS = ("木造", "木", "準耐火造")
_PRE_1981 = 1981
_FLOOD_HIGH_KEYS = {"3_5", "5_10", "ge_10"}
_FLOOD_LOW_KEYS = {"05_1", "1_3"}


def _detect_wood(structure: pd.Series, fire: pd.Series | None) -> pd.Series:
    s = structure.astype("string").fillna("")
    out = s.eq("wood")
    for tok in WOOD_STRUCTURE_TOKENS:
        if tok == "wood":
            continue
        out |= s.str.contains(tok, case=False, na=False)
    if fire is not None:
        f = fire.astype("string").fillna("")
        fallback = pd.Series(False, index=structure.index)
        for tok in _WOOD_FIRE_TOKENS:
            fallback |= f.str.contains(tok, case=False, na=False)
        out |= fallback & s.isin(["", "other"])
    return out


class RiskChoroplethPreset(BasePreset):
    metadata = PresetMetadata(
        id="risk_choropleth",
        name="Risk Choropleth",
        description="Pre-1981 wood buildings inside river-flood inundation zones — the plan's flagship intersection of era × structure × hazard.",
        modes=["static"],
        required_fields=[
            hazard_covered_col("river_flood"),
            hazard_depth_col("river_flood"),
        ],
        optional_fields=[COL_STRUCTURE, COL_YEAR_BUILT, COL_FIRE_RESISTANCE],
        required_hazards=["river_flood"],
        default_format="png",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        n = len(gdf)
        structure = (
            gdf[COL_STRUCTURE] if COL_STRUCTURE in gdf.columns
            else pd.Series([None] * n, index=gdf.index)
        )
        fire = gdf[COL_FIRE_RESISTANCE] if COL_FIRE_RESISTANCE in gdf.columns else None
        years = (
            pd.to_numeric(gdf[COL_YEAR_BUILT], errors="coerce")
            if COL_YEAR_BUILT in gdf.columns
            else pd.Series(np.nan, index=gdf.index)
        )
        # Three inputs need to be PRESENT for a building to leave the no_data
        # bucket: river-flood coverage, structure (wood / not-wood, NOT the
        # `other`/`""` collapse from plateau-bridge), and year_built. If any
        # of the three is missing the building stays `no_data`. This is the
        # contract for the plan's flagship "Risk Choropleth": era × structure
        # × hazard. Without all three, we can't make any of the assertions
        # the colour bands encode.
        structure_known = structure.astype("string").fillna("").isin([
            "wood", "rc", "steel", "src",  # plateau-bridge canonical enum
        ]) | structure.astype("string").fillna("").apply(
            lambda s: any(tok in s for tok in ("木", "RC", "S造", "鉄"))
        )
        year_known = years.notna() & (years >= 1850)
        is_wood = _detect_wood(structure, fire)
        is_pre81 = year_known & (years < _PRE_1981)
        depth_keys = assign_river_flood_keys(gdf)

        flood_high = depth_keys.isin(_FLOOD_HIGH_KEYS)
        flood_low = depth_keys.isin(_FLOOD_LOW_KEYS)
        hazard_no_data = depth_keys == "no_data"

        # `data_known` is the AND of every input dimension. Anything not in
        # this set is forced to no_data — no exceptions, no implicit "other".
        data_known = ~hazard_no_data & structure_known & year_known

        keys = pd.Series(["no_data"] * n, index=gdf.index, dtype="object")
        keys[data_known & is_wood & is_pre81 & flood_high] = "pre81_wood_flood_high"
        keys[data_known & is_wood & is_pre81 & flood_low] = "pre81_wood_flood_low"
        keys[data_known & is_wood & is_pre81 & ~flood_high & ~flood_low] = "pre81_wood_dry"
        rest_known = data_known & ~(is_wood & is_pre81)
        keys[rest_known & (flood_high | flood_low)] = "other_in_flood"
        keys[rest_known & ~flood_high & ~flood_low] = "other_dry"

        warnings: list[str] = []
        if dataset.field_coverage.get("structure", 0.0) < 0.5:
            warnings.append(
                f"structure coverage is {dataset.field_coverage.get('structure', 0.0):.0%} for {dataset.city!r}; "
                "wood detection falls back to fire_resistance and many buildings will be no_data."
            )
        if dataset.field_coverage.get("year_built", 0.0) < 0.5:
            warnings.append(
                f"year_built coverage is {dataset.field_coverage.get('year_built', 0.0):.0%} — without era we cannot prove pre-1981."
            )

        return PreparedData(
            dataset=dataset,
            derived={
                "risk_keys": keys,
                "n_headline": int((keys == "pre81_wood_flood_high").sum()),
                "n_no_data": int((keys == "no_data").sum()),
            },
            warnings=tuple(warnings),
        )

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys = prepared.derived["risk_keys"]
        palette = apply_theme_overrides(load_palette("risk_choropleth"), theme)
        key_list = keys.tolist()
        fills = [palette.color_for(k) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,

            fill_keys=key_list,
            z=10,
            semantic={"field": "risk_choropleth"},
        )
        entries = (
            LegendEntry(label="Pre-1981 wood · flood ≥3 m", color=palette.color_for("pre81_wood_flood_high")),
            LegendEntry(label="Pre-1981 wood · flood 0.5–3 m", color=palette.color_for("pre81_wood_flood_low")),
            LegendEntry(label="Pre-1981 wood · dry", color=palette.color_for("pre81_wood_dry")),
            LegendEntry(label="Other · in flood zone", color=palette.color_for("other_in_flood")),
            LegendEntry(label="Other · dry", color=palette.color_for("other_dry")),
            LegendEntry(label="No data", color=palette.color_for("no_data"), is_no_data=True),
        )
        legend = LegendSpec(
            title="Risk (wood × era × flood depth)",
            entries=entries,
            note="Headline red = pre-1981 wooden buildings inside ≥3 m flood inundation. Hashed grey = no data, never 'low risk'.",
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
                "n_headline": prepared.derived.get("n_headline", 0),
                "n_no_data": prepared.derived.get("n_no_data", 0),
            },
        )


PRESET = RiskChoroplethPreset()


def factory() -> RiskChoroplethPreset:
    return RiskChoroplethPreset()

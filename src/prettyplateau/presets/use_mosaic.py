"""Use Mosaic — every building coloured by its `usage` category.

This is the most-universal preset: `usage` is 100% populated across nearly all
PLATEAU cities, so the preset works out of the box for every Tokyo ward, Osaka,
Nagoya, Yokohama (note: Yokohama's usage coverage is 0% per the manifest, so
that city falls back to unknown grey).
"""

from __future__ import annotations

import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.schema import COL_USAGE
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

# Map raw plateau-bridge `usage` strings → palette keys.
# plateau-bridge's canonical Usage enum is {residential, commercial, industrial,
# educational, public, other}. Synonyms below are accepted defensively for
# older/forked datasets that pre-date the enum normalisation.
USAGE_KEY_MAP: dict[str, str] = {
    "residential": "residential",
    "commercial": "commercial",
    "industrial": "industrial",
    "public": "public",
    "educational": "educational",
    "education": "educational",
    "school": "educational",
    "medical": "medical",
    "hospital": "medical",
    "religious": "religious",
    "shrine": "religious",
    "temple": "religious",
    "transportation": "transportation",
    "transport": "transportation",
    "station": "transportation",
    "agriculture": "agriculture",
    "agricultural": "agriculture",
    "mixed": "mixed",
    "mixed-use": "mixed",
    "other": "other",
}


def _to_key(raw: object) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "unknown"
    s = str(raw).strip().lower()
    if not s:
        return "unknown"
    return USAGE_KEY_MAP.get(s, "other")


class UseMosaicPreset(BasePreset):
    metadata = PresetMetadata(
        id="use_mosaic",
        name="Use Mosaic",
        description="Per-building usage category. Reveals commercial spines and industrial enclaves.",
        modes=["static"],
        required_fields=[COL_USAGE],
        default_format="png",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        warnings: tuple[str, ...] = ()
        if COL_USAGE not in gdf.columns:
            keys = pd.Series(["unknown"] * len(gdf), index=gdf.index)
            warnings = (f"city {dataset.city!r} has no usage column; all buildings unknown.",)
        else:
            keys = gdf[COL_USAGE].map(_to_key).astype("string").fillna("unknown")
            coverage = dataset.field_coverage.get("usage", 0.0)
            if coverage < 0.5:
                warnings = (f"usage coverage is {coverage:.0%} for {dataset.city!r}.",)
        return PreparedData(dataset=dataset, derived={"usage_keys": keys}, warnings=warnings)

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys = prepared.derived["usage_keys"]
        palette = apply_theme_overrides(load_palette("use_category"), theme)

        key_list = keys.tolist()

        fills = [palette.color_for(k) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,

            fill_keys=key_list,
            z=10,
            semantic={"field": "usage"},
        )
        entries = tuple(
            LegendEntry(label=key.replace("_", " ").title(), color=palette.color_for(key))
            for key in palette.keys_in_order()
            if key != "unknown"
        ) + (
            LegendEntry(label="Unknown", color=palette.color_for("unknown"), is_no_data=True),
        )
        legend = LegendSpec(
            title="Building usage",
            entries=entries,
            note=None,
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
                "n_unknown": int((keys == "unknown").sum()),
            },
        )


PRESET = UseMosaicPreset()


def factory() -> UseMosaicPreset:
    return UseMosaicPreset()

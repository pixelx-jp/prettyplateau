"""Height Topo — every building coloured by `height`.

A "topo" map of the city built from per-building heights. The classic version
uses contour lines, but PLATEAU buildings are polygons, not a height raster, so
this v1 implementation uses an ordinal sequential palette. (A true contour
engine would aggregate building tops onto a grid; deferred to v2.)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.schema import COL_HEIGHT
from prettyplateau.presets._common import bbox_of_gdf
from prettyplateau.presets._layers import admin_boundary_layer
from prettyplateau.presets.base import BasePreset, PreparedData
from prettyplateau.presets.scene import (
    LegendEntry,
    LegendSpec,
    PolygonLayer,
    RenderScene,
)
from prettyplateau.style.theme import Theme

_HEIGHT_BUCKETS: tuple[tuple[float, float, str, str], ...] = (
    (0.0, 5.0, "h_0_5", "< 5 m"),
    (5.0, 10.0, "h_5_10", "5–10 m"),
    (10.0, 20.0, "h_10_20", "10–20 m"),
    (20.0, 40.0, "h_20_40", "20–40 m"),
    (40.0, 80.0, "h_40_80", "40–80 m"),
    (80.0, 150.0, "h_80_150", "80–150 m"),
    (150.0, float("inf"), "h_150_plus", "≥ 150 m"),
)

# A perceptually-uniform-ish viridis-inspired ramp.
_HEIGHT_PALETTE: dict[str, str] = {
    "h_0_5":      "#F4F1E1",
    "h_5_10":     "#DBE2B2",
    "h_10_20":    "#9EC68A",
    "h_20_40":    "#4AA08C",
    "h_40_80":    "#2C6F8E",
    "h_80_150":   "#2C3F7E",
    "h_150_plus": "#1B1B4B",
    "unknown":    "#C9CDD6",
}


def _bucket_keys(values: pd.Series) -> pd.Series:
    nums = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float, copy=False)
    out = np.full(nums.shape[0], "unknown", dtype=object)
    not_na = ~np.isnan(nums)
    for lo, hi, key, _label in _HEIGHT_BUCKETS:
        out[not_na & (nums >= lo) & (nums < hi)] = key
    return pd.Series(out, index=values.index, name="height_key")


class HeightTopoPreset(BasePreset):
    metadata = PresetMetadata(
        id="height_topo",
        name="Height Topo",
        description="Per-building height bucketed into a sequential ramp. Reveals city skyline shape.",
        modes=["static"],
        required_fields=[COL_HEIGHT],
        default_format="png",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        if COL_HEIGHT not in gdf.columns:
            keys = pd.Series(["unknown"] * len(gdf), index=gdf.index)
            warnings = (f"city {dataset.city!r} has no height column; all buildings unknown.",)
        else:
            keys = _bucket_keys(gdf[COL_HEIGHT])
            coverage = dataset.field_coverage.get("height", 0.0)
            warnings = (
                (f"height coverage is {coverage:.0%} for {dataset.city!r}.",)
                if coverage < 0.5
                else ()
            )
        return PreparedData(dataset=dataset, derived={"height_keys": keys}, warnings=warnings)

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys = prepared.derived["height_keys"]
        key_list = keys.tolist()
        fills = [_HEIGHT_PALETTE.get(k, _HEIGHT_PALETTE["unknown"]) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,
            fill_keys=key_list,
            z=10,
            semantic={"field": "height"},
        )
        boundary = admin_boundary_layer(ds, theme)
        entries = tuple(
            LegendEntry(label=label, color=_HEIGHT_PALETTE[key])
            for _, _, key, label in _HEIGHT_BUCKETS
        ) + (
            LegendEntry(label="Unknown", color=_HEIGHT_PALETTE["unknown"], is_no_data=True),
        )
        legend = LegendSpec(title="Building height", entries=entries)
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


PRESET = HeightTopoPreset()


def factory() -> HeightTopoPreset:
    return HeightTopoPreset()

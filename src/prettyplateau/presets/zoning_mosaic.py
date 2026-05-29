"""Zoning Mosaic — per-building zoning category.

plateau-bridge surfaces Japanese 用途地域 (use district zoning) in the
`zoning_use` column. The values are JSON arrays of one or more zoning
strings — when a building straddles boundaries it carries multiple — so
this preset collapses to the most-restrictive zone (first array element,
which plateau-bridge sorts canonically).

For Tokyo wards `zoning_use` is well populated. Where it's missing the
preset paints `unknown` grey — same invariant as elsewhere.
"""

from __future__ import annotations

import json

import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.schema import COL_ZONING_USE
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


# Mapping from canonical Japanese zoning names to short English category keys.
# These follow the standard MLIT 13-class scheme.
_ZONING_MAP: dict[str, str] = {
    "第1種低層住居専用地域": "low_res",
    "第2種低層住居専用地域": "low_res",
    "第1種中高層住居専用地域": "mid_res",
    "第2種中高層住居専用地域": "mid_res",
    "第1種住居地域": "res",
    "第2種住居地域": "res",
    "準住居地域": "res",
    "田園住居地域": "agri_res",
    "近隣商業地域": "near_commercial",
    "商業地域": "commercial",
    "準工業地域": "semi_industrial",
    "工業地域": "industrial",
    "工業専用地域": "industrial_only",
}

_ZONING_PALETTE: dict[str, str] = {
    "low_res":          "#F4E5A0",
    "mid_res":          "#E8C547",
    "res":              "#E78A2C",
    "agri_res":         "#A8C66C",
    "near_commercial":  "#E04E5C",
    "commercial":       "#C0392B",
    "semi_industrial":  "#6B7280",
    "industrial":       "#3F4858",
    "industrial_only":  "#1B1B2A",
    "other":            "#BBBBBB",
    "unknown":          "#C9CDD6",
}

_ZONING_LABELS: dict[str, str] = {
    "low_res":          "Low-rise residential (1類/2類低層)",
    "mid_res":          "Mid-rise residential (中高層)",
    "res":              "Residential (1住/2住/準住)",
    "agri_res":         "Agri-residential (田園住居)",
    "near_commercial":  "Neighbourhood commercial (近商)",
    "commercial":       "Commercial (商業)",
    "semi_industrial":  "Semi-industrial (準工業)",
    "industrial":       "Industrial (工業)",
    "industrial_only":  "Industrial-only (工業専用)",
    "other":            "Other zoning",
    "unknown":          "No zoning data",
}


def _to_key(raw: object) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "unknown"
    s = str(raw).strip()
    if not s:
        return "unknown"
    # plateau-bridge stores as JSON array string; first element is the canonical zone.
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if arr:
                s = str(arr[0])
        except json.JSONDecodeError:
            pass
    return _ZONING_MAP.get(s, "other")


class ZoningMosaicPreset(BasePreset):
    metadata = PresetMetadata(
        id="zoning_mosaic",
        name="Zoning Mosaic",
        description="Per-building 用途地域 zoning category (MLIT 13-class scheme).",
        modes=["static"],
        required_fields=[COL_ZONING_USE],
        default_format="png",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        if COL_ZONING_USE not in gdf.columns:
            keys = pd.Series(["unknown"] * len(gdf), index=gdf.index)
            warnings: tuple[str, ...] = (f"city {dataset.city!r} has no zoning_use column.",)
        else:
            keys = gdf[COL_ZONING_USE].map(_to_key).astype("string").fillna("unknown")
            n_unknown = int((keys == "unknown").sum())
            warnings = (
                (f"{n_unknown}/{len(gdf)} buildings have no zoning_use data.",)
                if n_unknown > 0
                else ()
            )
        return PreparedData(dataset=dataset, derived={"zoning_keys": keys}, warnings=warnings)

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys = prepared.derived["zoning_keys"]
        key_list = keys.tolist()
        fills = [_ZONING_PALETTE.get(k, _ZONING_PALETTE["unknown"]) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,

            fill_keys=key_list,
            z=10,
            semantic={"field": "zoning_use"},
        )
        # Build the legend in the canonical MLIT order so colour ↔ density of
        # use-restriction reads from low-rise residential through industrial.
        order = [
            "low_res", "mid_res", "res", "agri_res",
            "near_commercial", "commercial",
            "semi_industrial", "industrial", "industrial_only",
            "other",
        ]
        present = set(keys.unique())
        entries = tuple(
            LegendEntry(label=_ZONING_LABELS[k], color=_ZONING_PALETTE[k])
            for k in order
            if k in present
        ) + (
            (LegendEntry(label=_ZONING_LABELS["unknown"], color=_ZONING_PALETTE["unknown"], is_no_data=True),)
            if "unknown" in present
            else ()
        )
        legend = LegendSpec(
            title="Zoning (用途地域)",
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


PRESET = ZoningMosaicPreset()


def factory() -> ZoningMosaicPreset:
    return ZoningMosaicPreset()

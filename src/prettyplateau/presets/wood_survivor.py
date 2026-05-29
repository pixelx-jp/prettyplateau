"""Wood Survivor — pre-1945 wooden buildings still standing today.

The preset's narrative hook: "buildings that survived the firebombings and the
quakes". Implementation uses `structure` + `year_built`. Buildings without
either field render as grey-with-hash so they cannot be mistaken for "safe".

Requirement note
----------------

This preset is most meaningful in cities where both `structure` and `year_built`
are populated. Osaka has structure but not year_built; Sapporo & Fukuoka have
both. Tokyo wards currently have neither, so the preset will run but produce a
canvas dominated by unknown grey — that's a *truthful* output, not a failure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.filters import WOOD_STRUCTURE_TOKENS
from prettyplateau.data.schema import COL_FIRE_RESISTANCE, COL_STRUCTURE, COL_YEAR_BUILT
from prettyplateau.presets._common import bbox_of_gdf
from prettyplateau.presets._layers import admin_boundary_layer
from prettyplateau.presets.base import BasePreset, PreparedData
from prettyplateau.presets.scene import (
    LegendEntry,
    LegendSpec,
    PolygonLayer,
    RenderScene,
    TextAnnotation,
)
from prettyplateau.style.palette import apply_theme_overrides, load_palette
from prettyplateau.style.theme import Theme

_WOOD_FIRE_TOKENS = ("木造", "木", "準耐火造")
"""Fallback tokens for cities where `structure` is null but `fire_resistance`
contains structural clues. Note: this is a soft fallback — we never claim
something is wood from these tokens alone in metadata, but it's useful for
visual context in cities like the Tokyo wards."""


def _is_wood(structure: pd.Series, fire: pd.Series | None) -> pd.Series:
    out = pd.Series(False, index=structure.index)
    s = structure.astype("string").fillna("")
    # `==` against the canonical enum value first — fast path, no regex.
    out |= s.eq("wood")
    # Then partial-match the Japanese / mixed-case synonyms.
    for tok in WOOD_STRUCTURE_TOKENS:
        if tok == "wood":
            continue
        out |= s.str.contains(tok, case=False, na=False)
    if fire is not None:
        # Only use the fire-resistance fallback for rows where structure was
        # empty or coerced to the catch-all "other" bucket by plateau-bridge.
        unknown_struct = s.isin(["", "other"])
        f = fire.astype("string").fillna("")
        fallback = pd.Series(False, index=structure.index)
        for tok in _WOOD_FIRE_TOKENS:
            fallback |= f.str.contains(tok, case=False, na=False)
        out |= fallback & unknown_struct
    return out


class WoodSurvivorPreset(BasePreset):
    metadata = PresetMetadata(
        id="wood_survivor",
        name="Wood Survivor",
        description="Pre-1945 wooden buildings highlighted; later wood faded; non-wood neutral.",
        modes=["static"],
        required_fields=[COL_STRUCTURE],
        optional_fields=[COL_YEAR_BUILT, COL_FIRE_RESISTANCE],
        default_format="png",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        structure = gdf[COL_STRUCTURE] if COL_STRUCTURE in gdf.columns else pd.Series([None] * len(gdf), index=gdf.index)
        fire = gdf[COL_FIRE_RESISTANCE] if COL_FIRE_RESISTANCE in gdf.columns else None
        years = pd.to_numeric(gdf[COL_YEAR_BUILT], errors="coerce") if COL_YEAR_BUILT in gdf.columns else pd.Series(np.nan, index=gdf.index)

        is_wood = _is_wood(structure, fire)
        keys = pd.Series(["unknown"] * len(gdf), index=gdf.index, dtype="object")
        struct_known = structure.notna() & (structure.astype("string").fillna("") != "")
        # Non-wood and structure-known
        keys[(~is_wood) & struct_known] = "non_wood"
        # Wood, year known
        year_valid = years.notna() & (years >= 1850)  # filter out the year=1 sentinel
        wood_pre = is_wood & year_valid & (years < 1946)
        wood_mid = is_wood & year_valid & (years >= 1946) & (years < 1981)
        wood_post = is_wood & year_valid & (years >= 1981)
        keys[wood_pre] = "wood_pre1945"
        keys[wood_mid] = "wood_1946_1980"
        keys[wood_post] = "wood_post1980"
        # Confirmed wood with NO year evidence is its own bucket — never
        # bucketed as "post-1980" because absence of year ≠ proof of modernity.
        # The plan's flagship narrative is "1945 前 survivors", and silently
        # rolling unknown-year wood into post-1980 would *understate* the
        # survivor population and contradict the framing.
        wood_unknown_year = is_wood & ~year_valid
        keys[wood_unknown_year] = "wood_year_unknown"

        warnings: list[str] = []
        if dataset.field_coverage.get("structure", 0.0) < 0.5:
            warnings.append(
                f"structure coverage is {dataset.field_coverage.get('structure', 0.0):.0%} for {dataset.city!r}; "
                "many buildings will be unknown.",
            )
        if dataset.field_coverage.get("year_built", 0.0) < 0.5:
            warnings.append(
                "year_built coverage is below 50%; wooden buildings with unknown year "
                "go into their own `wood_year_unknown` bucket — never inferred as modern.",
            )

        return PreparedData(dataset=dataset, derived={"wood_keys": keys, "n_wood_pre1945": int(wood_pre.sum())}, warnings=tuple(warnings))

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys = prepared.derived["wood_keys"]
        palette = apply_theme_overrides(load_palette("wood_survivor"), theme)

        key_list = keys.tolist()

        fills = [palette.color_for(k) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,

            fill_keys=key_list,
            z=10,
            semantic={"field": "wood_survivor"},
        )

        entries = (
            LegendEntry(label="Wood, pre-1945", color=palette.color_for("wood_pre1945")),
            LegendEntry(label="Wood, 1946–1980", color=palette.color_for("wood_1946_1980")),
            LegendEntry(label="Wood, 1981+", color=palette.color_for("wood_post1980")),
            LegendEntry(
                label="Wood, year unknown",
                color=palette.color_for("wood_year_unknown"),
                is_no_data=True,
            ),
            LegendEntry(label="Non-wood", color=palette.color_for("non_wood")),
            LegendEntry(label="Unknown / no data", color=palette.color_for("unknown"), is_no_data=True),
        )
        legend = LegendSpec(
            title="Structure × Year",
            entries=entries,
            note="Pre-1945 wood = survived war + earthquakes. Grey = structure or year unknown — never inferred as modern.",
        )
        boundary = admin_boundary_layer(ds, theme)
        layers = (boundary, layer) if boundary else (layer,)
        # Plan: "1945 前现存木造建筑分布 (战火幸存者地图); 红色高亮 + 空袭范围参考".
        # We can't ship a 1945 firebombing damage polygon without external
        # data, but we annotate the canvas with the historical context so a
        # reader unfamiliar with the Tōkyō air-raids doesn't mistake the
        # red highlight for an arbitrary "old wood" map.
        annotations: tuple[TextAnnotation, ...] = (
            TextAnnotation(
                text="Red = wooden buildings predating the 1945 Tōkyō firebombings (air-raid survivors).",
                x=0.5,
                y=0.135,
                align="center",
                valign="bottom",
                color=theme.muted,
                size=8.0,
                z=9_400,
            ),
        )
        return RenderScene(
            bounds=bbox_of_gdf(gdf),
            background=theme.background,
            layers=layers,
            legend=legend,
            annotations=annotations,
            semantic_metadata={
                "preset": self.metadata.id,
                "n_buildings": int(len(gdf)),
                "n_wood_pre1945": prepared.derived.get("n_wood_pre1945", 0),
            },
        )


PRESET = WoodSurvivorPreset()


def factory() -> WoodSurvivorPreset:
    return WoodSurvivorPreset()

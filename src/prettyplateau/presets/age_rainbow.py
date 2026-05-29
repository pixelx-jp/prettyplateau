"""Building Age Rainbow — every building coloured by `year_built`.

This preset is the flagship of prettyplateau and the headline claim in the
launch tweet. It deliberately exposes PLATEAU's per-building year-built
attribute, which OpenStreetMap-derived map projects cannot match.

Coverage caveat
---------------

PLATEAU's `year_built` coverage is uneven: Fukuoka and Sapporo are 100%,
most Tokyo wards are 0%. Buildings with no year are rendered as **unknown gray**
and surfaced as a legend entry — never silently dropped, never inferred.
"""

from __future__ import annotations

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.data.schema import COL_YEAR_BUILT
from prettyplateau.presets._common import AGE_BUCKETS, assign_age_keys, bbox_of_gdf
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


class AgeRainbowPreset(BasePreset):
    metadata = PresetMetadata(
        id="age_rainbow",
        name="Building Age Rainbow",
        description="Per-building year_built, bucketed into colour bands. Unknown stays grey.",
        modes=["static"],
        required_fields=[COL_YEAR_BUILT],
        optional_fields=[],
        default_format="png",
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        keys = assign_age_keys(gdf[COL_YEAR_BUILT]) if COL_YEAR_BUILT in gdf.columns else None
        if keys is None:
            warnings = (
                f"city {dataset.city!r} has no year_built column; all buildings rendered as unknown.",
            )
            keys = assign_age_keys(gdf.iloc[:, 0].where(lambda _: False))  # all NaN
        else:
            coverage = dataset.field_coverage.get("year_built", 0.0)
            warnings = ()
            if coverage < 0.5:
                warnings = (
                    f"year_built coverage is {coverage:.0%} for {dataset.city!r}; "
                    "most buildings will appear as unknown grey.",
                )
        return PreparedData(dataset=dataset, derived={"age_keys": keys}, warnings=warnings)

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        gdf = ds.gdf
        keys = prepared.derived["age_keys"]
        palette = apply_theme_overrides(load_palette("age_rainbow"), theme)

        key_list = keys.tolist()
        fills = [palette.color_for(k) for k in key_list]
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,
            fill_keys=key_list,
            edge_color=None,
            edge_width=0.0,
            alpha=1.0,
            z=10,
            semantic={"field": "year_built"},
        )
        legend = LegendSpec(
            title="Year built",
            entries=tuple(
                LegendEntry(label=label, color=palette.color_for(key))
                for _, _, key, label in AGE_BUCKETS
            )
            + (
                LegendEntry(
                    label="Unknown / no data",
                    color=palette.color_for("unknown"),
                    is_no_data=True,
                ),
            ),
            note="Grey = no year-built data in PLATEAU for this building.",
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


PRESET = AgeRainbowPreset()


def factory() -> AgeRainbowPreset:
    return AgeRainbowPreset()

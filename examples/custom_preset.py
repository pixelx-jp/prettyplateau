"""Build a one-off preset inline without packaging it.

For contributors prototyping new visualizations. The same shape — subclass
`BasePreset`, return a `RenderScene` — works whether you ship the preset
as its own pip package (see `prettyplateau create-preset`) or just keep it
in your local script.

  uv run examples/custom_preset.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.compose.attribution_injector import (
    AttributionInjector,
    AttributionSpec,
)
from prettyplateau.compose.composer import Composer, CompositionOptions
from prettyplateau.data.access import CityDataset, DataAccess
from prettyplateau.export.png import PNGExporter
from prettyplateau.presets._common import bbox_of_gdf
from prettyplateau.presets.base import BasePreset, PreparedData
from prettyplateau.presets.scene import (
    LegendEntry,
    LegendSpec,
    PolygonLayer,
    RenderScene,
)
from prettyplateau.renderers.matplotlib_renderer import (
    MatplotlibRenderer,
    RenderOptions,
)
from prettyplateau.style.theme import Theme, get_theme
import datetime as _dt


class TallBuildingsHighlight(BasePreset):
    """Buildings ≥ 60 m glow orange; everything else is dimmed grey.

    Two lines of preset logic, one palette key. The point is to show that
    presets aren't a heavy framework — they're just data → scene.
    """

    metadata = PresetMetadata(
        id="custom_tall_buildings",
        name="Tall Buildings",
        description="Highlight buildings 60m or taller.",
        modes=["static"],
        required_fields=["height"],
        community=True,
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        heights = pd.to_numeric(dataset.gdf["height"], errors="coerce")
        keys = pd.Series(["short"] * len(dataset.gdf), index=dataset.gdf.index, dtype="object")
        keys[heights >= 60] = "tall"
        return PreparedData(dataset=dataset, derived={"keys": keys})

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        gdf = prepared.dataset.gdf
        keys = prepared.derived["keys"]
        palette = {"tall": "#E78A2C", "short": "#E5E7EB"}
        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=[palette[k] for k in keys.tolist()],
            z=10,
        )
        legend = LegendSpec(
            title="Building height",
            entries=(
                LegendEntry(label="≥ 60 m", color=palette["tall"]),
                LegendEntry(label="< 60 m", color=palette["short"]),
            ),
        )
        return RenderScene(
            bounds=bbox_of_gdf(gdf),
            background=theme.background,
            layers=(layer,),
            legend=legend,
            semantic_metadata={"preset": self.metadata.id, "n_buildings": int(len(gdf))},
        )


def main() -> None:
    access = DataAccess(data_root="../plateau-core")
    dataset = access.load_city("minato")
    preset = TallBuildingsHighlight()
    request = RenderRequest(city="minato", preset=preset.metadata.id)
    prepared = preset.prepare(dataset, request)
    theme = get_theme("default")
    scene = preset.build_scene(prepared, theme, request)

    opts = CompositionOptions(title="Minato — Tall Buildings", subtitle="Inline custom preset · PLATEAU 2023")
    fig = MatplotlibRenderer().render(
        scene,
        theme,
        RenderOptions(
            width_px=2400,
            top_margin=opts.top_margin(),
            bottom_margin=opts.bottom_margin(),
            side_margin=opts.side_margin(),
        ),
    )
    composition = Composer(
        AttributionInjector(
            AttributionSpec(
                text=dataset.attribution,
                dataset_id=dataset.dataset_id,
                generated_at=_dt.datetime.now(tz=_dt.timezone.utc),
            )
        )
    ).compose(fig, scene, theme, opts)

    out = Path(__file__).parent / "out" / "minato_tall_buildings.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    PNGExporter().write(
        composition,
        out,
        metadata={
            "Software": "prettyplateau-example",
            "Attribution": dataset.attribution,
            "Preset": preset.metadata.id,
            "City": dataset.city,
            "Theme": "default",
            "DatasetID": dataset.dataset_id or "",
            "GeneratedAt": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        },
        overwrite=True,
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

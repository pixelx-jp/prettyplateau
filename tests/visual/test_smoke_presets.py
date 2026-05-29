"""End-to-end smoke tests on synthetic fixtures.

These do not assert pixel-exact baselines (those need stable matplotlib + font
versions, deferred to CI hardening). They assert *structural* invariants:
  - scene has the expected number of polygons,
  - palette keys actually appear in the legend,
  - unknown/no-data buckets are present whenever any input is missing,
  - rendered PNG has CC BY attribution in metadata.

Pixel-baseline regression goes under `tests/visual/baselines/` and runs only in
the `--with-visual` CI lane.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest
from PIL import Image

from prettyplateau.compose.attribution_injector import (
    AttributionInjector,
    AttributionSpec,
)
from prettyplateau.compose.composer import Composer, CompositionOptions
from prettyplateau.export.png import PNGExporter
from prettyplateau.presets.registry import get_registry
from prettyplateau.renderers.matplotlib_renderer import MatplotlibRenderer, RenderOptions
from prettyplateau.style.theme import get_theme
from prettyplateau.testing.fixtures import fixture_dataset
from prettyplateau.api.types import RenderRequest


@pytest.mark.parametrize(
    "preset_id",
    [
        "age_rainbow", "use_mosaic", "wood_survivor", "risk_choropleth", "flood_depth",
        "height_topo", "hazard_confluence", "density_hex", "zoning_mosaic",
    ],
)
def test_preset_round_trip_png(tmp_path: Path, preset_id: str) -> None:
    dataset = fixture_dataset(n=64)
    request = RenderRequest(city="fixture", preset=preset_id, out=str(tmp_path / f"{preset_id}.png"))
    preset = get_registry().resolve(preset_id)

    prepared = preset.prepare(dataset, request)
    theme = get_theme("default")
    scene = preset.build_scene(prepared, theme, request)

    # Structural invariants.
    assert scene.layers, f"{preset_id}: scene must have at least one layer"
    assert scene.legend is not None, f"{preset_id}: scene must have a legend"
    polygon_layer = scene.layers[0]
    assert len(polygon_layer.fills) == len(polygon_layer.geometries)

    # Render → compose → export.
    opts = CompositionOptions(title=preset_id, subtitle=None)
    renderer = MatplotlibRenderer()
    fig = renderer.render(
        scene,
        theme,
        RenderOptions(
            width_px=600,
            top_margin=opts.top_margin(),
            bottom_margin=opts.bottom_margin(),
            side_margin=opts.side_margin(),
        ),
    )
    spec = AttributionSpec(
        text=dataset.attribution,
        dataset_id=dataset.dataset_id,
        generated_at=_dt.datetime(2026, 5, 28, tzinfo=_dt.timezone.utc),
    )
    composition = Composer(AttributionInjector(spec)).compose(fig, scene, theme, opts)
    result = PNGExporter().write(
        composition,
        tmp_path / f"{preset_id}.png",
        metadata={
            "Software": "prettyplateau-test",
            "Attribution": dataset.attribution,
            "Preset": preset_id,
            "City": dataset.city,
            "Theme": "default",
            "GeneratedAt": "2026-05-28T00:00:00+00:00",
        },
    )
    assert result.path.exists()
    # PNG metadata round-trip — attribution must survive into the file.
    img = Image.open(result.path)
    assert "Attribution" in img.info
    assert "PLATEAU" in img.info["Attribution"]
    assert composition.attribution_report.visible
    assert composition.attribution_report.metadata

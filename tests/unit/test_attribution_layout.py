"""Plan-mandated layout test: "attribution 不与图例重叠".

After composing, locate the attribution text and the legend axes in figure-
fraction coordinates and assert they don't overlap. This catches regressions
where someone shrinks the bottom margin or grows the legend without
accounting for the attribution band.
"""

from __future__ import annotations

import datetime as _dt

from matplotlib.transforms import Bbox

from prettyplateau.api.types import RenderRequest
from prettyplateau.compose.attribution_injector import AttributionInjector, AttributionSpec
from prettyplateau.compose.composer import Composer, CompositionOptions
from prettyplateau.presets.registry import get_registry
from prettyplateau.renderers.matplotlib_renderer import MatplotlibRenderer, RenderOptions
from prettyplateau.style.theme import get_theme
from prettyplateau.testing.fixtures import fixture_dataset


def _compose_fixture():
    dataset = fixture_dataset(n=24)
    preset = get_registry().resolve("use_mosaic")
    request = RenderRequest(city="fixture", preset="use_mosaic", title="layout test", subtitle="fixture")
    prepared = preset.prepare(dataset, request)
    theme = get_theme("default")
    scene = preset.build_scene(prepared, theme, request)
    opts = CompositionOptions(title="layout test", subtitle="fixture", show_legend=True, show_attribution=True)
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
    spec = AttributionSpec(
        text=dataset.attribution,
        dataset_id=dataset.dataset_id,
        generated_at=_dt.datetime(2026, 5, 29, tzinfo=_dt.timezone.utc),
    )
    composition = Composer(AttributionInjector(spec)).compose(fig, scene, theme, opts)
    return composition


def _bbox_of_text(fig, text_obj) -> Bbox:
    """Return the text's bounding box in figure-fraction coordinates."""
    renderer = fig.canvas.get_renderer() if hasattr(fig.canvas, "get_renderer") else None
    if renderer is None:
        # Force a draw to ensure renderer exists.
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(fig).draw()
        renderer = fig.canvas.get_renderer()
    bbox_display = text_obj.get_window_extent(renderer=renderer)
    return bbox_display.transformed(fig.transFigure.inverted())


def test_attribution_does_not_overlap_legend() -> None:
    composition = _compose_fixture()
    fig = composition.figure

    # Identify the attribution text — bottom-right by default, 7.5pt, contains "PLATEAU".
    attribution_texts = [t for t in fig.texts if "PLATEAU" in t.get_text()]
    assert attribution_texts, "no PLATEAU attribution text found on figure"
    attribution = attribution_texts[0]

    # Identify legend axes — they're the small axes (height <= 0.10) added by the composer.
    legend_axes = [
        ax for ax in fig.axes
        if ax.get_position().height <= 0.10 and ax.get_position().width >= 0.5
    ]
    assert legend_axes, "no legend axis found on figure"

    attribution_bbox = _bbox_of_text(fig, attribution)
    for legend_ax in legend_axes:
        legend_bbox = legend_ax.get_position()
        # Two bboxes overlap iff neither is strictly above/below/left/right of the other.
        no_overlap = (
            attribution_bbox.y1 <= legend_bbox.y0
            or attribution_bbox.y0 >= legend_bbox.y1
            or attribution_bbox.x1 <= legend_bbox.x0
            or attribution_bbox.x0 >= legend_bbox.x1
        )
        assert no_overlap, (
            f"attribution bbox {tuple(attribution_bbox.bounds)} overlaps legend "
            f"axes bbox {tuple(legend_bbox.bounds)}; reduce legend height or "
            f"raise its y-anchor"
        )

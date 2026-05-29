"""Animator — turns a preset's `TimelineSpec` into a stream of rendered frames.

The animator does NOT know how to encode video; it yields RGBA buffers and
lets the video exporter handle codec choices. This keeps `imageio-ffmpeg` (or
moviepy, or anything else) as an optional dependency.

Perf
----

Frame 0 builds the matplotlib figure with all geometry baked into a
`PatchCollection`. Every subsequent frame reuses the same figure and only:

  - replaces the facecolor array on the buildings layer,
  - updates the dynamic subtitle (e.g. "≤ 1990"),
  - redraws the canvas.

That brings 12-frame Fukuoka (355k polygons) from ~5 min to ~1 min on
a M-series MacBook, and scales linearly with frames thereafter rather than
with frames × buildings.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from matplotlib.figure import Figure

from prettyplateau.animation.captions import overlay_caption
from prettyplateau.compose.attribution_injector import AttributionInjector
from prettyplateau.compose.composer import Composer, CompositionOptions
from prettyplateau.presets.base import TimelineSpec
from prettyplateau.presets.scene import PolygonLayer
from prettyplateau.renderers.matplotlib_renderer import (
    MatplotlibRenderer,
    RenderOptions,
)
from prettyplateau.style.theme import Theme


@dataclass
class RenderedFrame:
    index: int
    t: float
    label: str
    rgba: np.ndarray  # (H, W, 4) uint8


class Animator:
    def __init__(
        self,
        renderer: MatplotlibRenderer,
        composer: Composer,
        attribution: AttributionInjector,
    ) -> None:
        self.renderer = renderer
        self.composer = composer
        self.attribution = attribution

    def stream(
        self,
        timeline: TimelineSpec,
        theme: Theme,
        render_opts: RenderOptions,
        title: str | None,
        subtitle: str | None,
    ) -> Iterator[RenderedFrame]:
        if not timeline.frames:
            return

        first = timeline.frames[0]
        persistent = self.renderer.render_persistent(first.scene, theme, render_opts)
        # Compose once: title + legend + attribution are static across frames.
        # The dynamic subtitle is per-frame and updated below.
        static_opts = CompositionOptions(
            title=title,
            subtitle=subtitle or first.label,
            show_legend=True,
            show_attribution=True,
        )
        self.composer.compose(persistent.figure, first.scene, theme, static_opts)
        # Plan: "`Surviving Buildings Timeline` 必须默认带说明文字" — the
        # caption is non-optional for any preset that ships one. We embed it
        # on the persistent canvas so every frame in the stream carries it,
        # not just the static export at the end.
        overlay_caption(persistent.figure, timeline.caption, color=theme.muted)
        subtitle_text = self._find_subtitle_text(persistent.figure)

        yield RenderedFrame(
            index=0,
            t=first.t,
            label=first.label,
            rgba=_fig_to_rgba(persistent.figure),
        )

        for i, frame in enumerate(timeline.frames[1:], start=1):
            # Update fills on the buildings layer in place.
            for layer in frame.scene.layers:
                if isinstance(layer, PolygonLayer):
                    self.renderer.update_layer_fills(persistent, layer.id, list(layer.fills))
            # Update dynamic subtitle to match the new frame.
            if subtitle_text is not None:
                subtitle_text.set_text(subtitle or frame.label)
            yield RenderedFrame(
                index=i,
                t=frame.t,
                label=frame.label,
                rgba=_fig_to_rgba(persistent.figure),
            )

    @staticmethod
    def _find_subtitle_text(figure: Figure):
        """Locate the subtitle text we just placed so we can mutate it per frame.

        The composer creates its subtitle at a known position (left, near top)
        — there's only one Text object at that anchor, so a positional match
        is sufficient and avoids leaking composer internals.
        """
        for child in figure.texts:
            if child.get_position()[1] > 0.9 and child.get_position()[1] < 0.97 and child.get_fontsize() < 16:
                return child
        return None


def _fig_to_rgba(fig: Figure) -> np.ndarray:
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    # Re-attach an Agg canvas only if the figure doesn't already have one;
    # reusing the canvas across frames is what makes the redraw cheap.
    canvas = getattr(fig, "canvas", None)
    if not isinstance(canvas, FigureCanvasAgg):
        canvas = FigureCanvasAgg(fig)
    canvas.draw()
    w, h = canvas.get_width_height()
    buf = np.frombuffer(canvas.buffer_rgba(), dtype=np.uint8)
    return buf.reshape(h, w, 4).copy()

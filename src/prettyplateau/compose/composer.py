"""Composer — adds title, subtitle, legend, attribution to a rendered scene.

The composer leaves the scene Figure intact and overlays via figure-fraction
text and a separate legend axis. It does *not* touch data and *cannot* skip
attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from matplotlib.figure import Figure
from matplotlib.patches import Patch

from prettyplateau.compose.attribution_injector import (
    AttributionInjectionReport,
    AttributionInjector,
)
from prettyplateau.presets.scene import LegendSpec, RenderScene
from prettyplateau.style import typography
from prettyplateau.style.theme import Theme


@dataclass(frozen=True)
class CompositionOptions:
    title: str | None = None
    subtitle: str | None = None
    show_legend: bool = True
    legend_position: Literal["bottom", "right"] = "bottom"
    show_attribution: bool = True  # may be False ONLY for intermediate artifacts
    # When show_attribution=False, AttributionInjector still records the obligation
    # in the result metadata so an exporter cannot ship an attribution-less file.

    def top_margin(self) -> float:
        """How much of the figure should be reserved above the map."""
        if self.title and self.subtitle:
            return 0.07
        if self.title or self.subtitle:
            return 0.05
        return 0.015

    def bottom_margin(self) -> float:
        """How much of the figure should be reserved below the map."""
        m = 0.02  # attribution + breathing room
        if self.show_legend and self.legend_position == "bottom":
            m += 0.10
        return m

    def side_margin(self) -> float:
        if self.show_legend and self.legend_position == "right":
            return 0.20
        return 0.015


@dataclass
class ComposedArtifact:
    figure: Figure
    attribution_report: AttributionInjectionReport = field(default_factory=AttributionInjectionReport)
    legend_drawn: bool = False
    title_drawn: bool = False


class Composer:
    def __init__(self, attribution: AttributionInjector) -> None:
        self.attribution = attribution

    def compose(
        self,
        figure: Figure,
        scene: RenderScene,
        theme: Theme,
        options: CompositionOptions,
    ) -> ComposedArtifact:
        result = ComposedArtifact(figure=figure)

        # Vertical anchor: just above the map area (which spans up to 1 - top_margin).
        top_band_top = 0.985
        side_pad = max(options.side_margin(), 0.04)
        # Auto-shrink fonts when the canvas is narrow. Plan default is 4K
        # (3840px wide) and the 22pt title looks right there; on a 1200px
        # preview canvas we'd be at half scale, so the title would overlap
        # the subtitle. Reference at 8 inches (≈2400px at 300dpi).
        fig_w_in = figure.get_size_inches()[0]
        scale = max(min(fig_w_in / 8.0, 1.0), 0.6)
        title_pt = max(typography.TITLE_PT * scale, 14)
        subtitle_pt = max(typography.SUBTITLE_PT * scale, 8)
        subtitle_offset = 0.03 * scale + 0.012
        if options.title:
            figure.text(
                side_pad,
                top_band_top,
                options.title,
                color=theme.foreground,
                fontsize=title_pt,
                fontweight="bold",
                ha="left",
                va="top",
                zorder=9_000,
            )
            result.title_drawn = True
        if options.subtitle:
            figure.text(
                side_pad,
                top_band_top - subtitle_offset,
                options.subtitle,
                color=theme.muted,
                fontsize=subtitle_pt,
                ha="left",
                va="top",
                zorder=9_000,
            )

        if options.show_legend and scene.legend is not None:
            self._draw_legend(figure, scene.legend, theme, options.legend_position)
            result.legend_drawn = True

        # Annotations defined by the scene.
        for ann in scene.annotations:
            figure.text(
                ann.x,
                ann.y,
                ann.text,
                color=ann.color,
                fontsize=ann.size,
                ha=ann.align,
                va=ann.valign,
                rotation=ann.rotation,
                zorder=ann.z,
            )

        if options.show_attribution:
            result.attribution_report = self.attribution.inject_into_figure(figure, theme)
        if getattr(theme, "paper_texture", False):
            self._overlay_paper_texture(figure, theme)
        return result

    @staticmethod
    def _overlay_paper_texture(figure, theme) -> None:
        """Draw a subtle warm-grey noise wash over the whole figure.

        Used by the `print` theme to suggest paper grain in the final PDF /
        PNG. The wash is deliberately faint (~3% opacity) so it never
        obscures the data — it just nudges the perceived medium from
        "screen" toward "paper".
        """
        import numpy as np

        rng = np.random.default_rng(seed=42)
        # 256-tile of normally distributed values, gamma'd to give a slight
        # warm cast.
        tile = rng.normal(loc=0.5, scale=0.06, size=(256, 256))
        tile = np.clip(tile, 0.3, 0.7)
        ax = figure.add_axes((0, 0, 1, 1), zorder=12_000, frameon=False)
        ax.set_axis_off()
        ax.imshow(tile, cmap="bone", alpha=0.04, aspect="auto", interpolation="bilinear")

    def _draw_legend(
        self,
        figure: Figure,
        spec: LegendSpec,
        theme: Theme,
        position: Literal["bottom", "right"],
    ) -> None:
        # Use a dedicated invisible axis so the legend doesn't fight the main map axis.
        if position == "bottom":
            # Sit above the attribution band. The attribution text height
            # in figure-fraction terms scales as 1/fig_height; at small
            # canvases we have to push the legend further up to avoid
            # collision. Empirically y=0.10 keeps a clear gap from 4×5 in
            # all the way to 8×10 in poster sizes.
            fig_h_in = figure.get_size_inches()[1]
            attribution_clearance = max(7.5 * 1.4 / (72 * fig_h_in), 0.025)
            legend_y = attribution_clearance + 0.025
            ax = figure.add_axes((0.04, legend_y, 0.92, 0.08))
        else:
            ax = figure.add_axes((0.80, 0.10, 0.18, 0.80))
        ax.set_axis_off()
        handles = []
        labels = []
        for entry in spec.entries:
            hatch = "///" if entry.is_no_data else None
            handles.append(
                Patch(
                    facecolor=entry.color,
                    edgecolor=theme.foreground if entry.is_no_data else "none",
                    hatch=hatch,
                    linewidth=0.4 if entry.is_no_data else 0.0,
                )
            )
            labels.append(entry.label)
        # Wrap legend entries onto multiple rows if there are many. At
        # narrow canvas widths the per-entry text gets cropped, so we
        # cap ncol more aggressively.
        if position == "bottom":
            fig_w_in = figure.get_size_inches()[0]
            max_per_row = 6 if fig_w_in >= 7 else (4 if fig_w_in >= 4.5 else 3)
            ncol = min(len(handles), max_per_row)
        else:
            ncol = 1
        legend = ax.legend(
            handles,
            labels,
            title=spec.title,
            loc="center",
            frameon=False,
            ncol=ncol,
            fontsize=9,
            title_fontsize=10,
            labelcolor=theme.foreground,
        )
        for text in legend.get_texts():
            text.set_color(theme.foreground)
        legend.get_title().set_color(theme.foreground)
        if spec.note:
            ax.text(
                0.5,
                -0.05 if position == "bottom" else -0.02,
                spec.note,
                ha="center",
                va="top",
                fontsize=8,
                color=theme.muted,
                transform=ax.transAxes,
            )

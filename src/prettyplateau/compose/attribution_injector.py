"""Attribution injection — mandatory, non-bypassable.

There is no public toggle here, by design. The CLI and API never expose a
"disable attribution" flag. If you find yourself wanting one, the answer is to
publish under a different licence — PLATEAU's CC BY 4.0 requires this.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Literal

from prettyplateau.core.errors import AttributionError


@dataclass(frozen=True)
class AttributionSpec:
    """The text that must be embedded into every artifact."""

    text: str
    dataset_id: str | None
    generated_at: _dt.datetime
    extra_lines: tuple[str, ...] = ()

    def primary_line(self) -> str:
        date = self.generated_at.strftime("%Y-%m-%d")
        parts = [self.text]
        if self.dataset_id:
            parts.append(self.dataset_id)
        parts.append(date)
        return " · ".join(parts)

    def all_lines(self) -> list[str]:
        return [self.primary_line(), *self.extra_lines]


@dataclass(frozen=True)
class AttributionStyle:
    """Visual style for the on-canvas attribution text.

    Position is restricted to a corner — a "free placement" knob is exactly the
    kind of foot-gun that lets a user hide attribution under a logo.
    """

    corner: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = "bottom-right"
    color: str | None = None  # default chosen from theme
    background: str | None = None  # optional pill behind text on dark/transparent canvases
    size_pt: float = 7.5
    padding_pt: float = 12.0
    language: Literal["en", "ja"] = "en"


@dataclass
class AttributionInjectionReport:
    visible: bool = False
    metadata: bool = False
    notes: list[str] = field(default_factory=list)

    def require_visible_and_metadata(self) -> None:
        if not (self.visible and self.metadata):
            raise AttributionError(
                f"attribution injection incomplete: visible={self.visible} metadata={self.metadata}"
            )


class AttributionInjector:
    """Owns the contract; specific exporters call into it with their backend."""

    def __init__(self, spec: AttributionSpec, style: AttributionStyle | None = None) -> None:
        if not spec.text:
            raise AttributionError("attribution text is empty; refusing to export")
        self.spec = spec
        self.style = style or AttributionStyle()

    def inject_into_figure(self, fig, theme) -> AttributionInjectionReport:
        """Draw attribution onto a matplotlib Figure. Used by PDF/SVG exporters
        and by the PNG composer when not deferring to Pillow."""
        from matplotlib.transforms import IdentityTransform

        text = self.spec.primary_line()
        color = self.style.color or theme.foreground

        # Position in figure-fraction coordinates so the corner is stable
        # regardless of the inner axes layout.
        pad = self.style.padding_pt / (72 * fig.get_size_inches()[0])
        pad_v = self.style.padding_pt / (72 * fig.get_size_inches()[1])
        corners = {
            "bottom-right": (1 - pad, pad_v, "right", "bottom"),
            "bottom-left": (pad, pad_v, "left", "bottom"),
            "top-right": (1 - pad, 1 - pad_v, "right", "top"),
            "top-left": (pad, 1 - pad_v, "left", "top"),
        }
        x, y, ha, va = corners[self.style.corner]
        fig.text(
            x,
            y,
            text,
            ha=ha,
            va=va,
            color=color,
            fontsize=self.style.size_pt,
            transform=fig.transFigure,
            zorder=10_000,
        )
        # Identity transform unused, kept import contained for future ext.
        del IdentityTransform
        return AttributionInjectionReport(visible=True, metadata=False)

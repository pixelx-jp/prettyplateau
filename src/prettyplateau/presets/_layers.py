"""Shared scene layers reused across built-in presets.

These helpers exist so every preset gets the same admin-boundary silhouette
without copy-pasting matplotlib styling into a dozen build_scene methods.
"""

from __future__ import annotations

from prettyplateau.data.access import CityDataset
from prettyplateau.presets.scene import PolygonLayer
from prettyplateau.style.theme import Theme


def admin_boundary_layer(dataset: CityDataset, theme: Theme) -> PolygonLayer | None:
    """Return a low-z boundary layer for the city, or None if no boundary data.

    Drawn as a near-invisible fill plus a thin dark outline so the city's
    silhouette reads even where buildings are sparse (parks, water,
    industrial sites). The fill is set to the theme background with a
    nudge toward the foreground so it's visible against transparent or
    paper-textured themes.
    """
    if dataset.admin_boundary is None or dataset.admin_boundary.is_empty:
        return None
    return PolygonLayer(
        id="admin_boundary",
        geometries=[dataset.admin_boundary],
        fills=[_blend(theme.background, theme.foreground, alpha=0.02)],
        edge_color=theme.muted,
        edge_width=0.4,
        alpha=1.0,
        z=0,  # underneath buildings (z=10) but above background.
        semantic={"role": "city_outline"},
    )


def _blend(base_hex: str, mix_hex: str, alpha: float) -> str:
    """Mix two hex colours in sRGB; small `alpha` keeps it close to `base`."""
    base = _hex_to_rgb(base_hex)
    mix = _hex_to_rgb(mix_hex)
    out = tuple(int(b * (1 - alpha) + m * alpha) for b, m in zip(base, mix, strict=False))
    return "#{:02X}{:02X}{:02X}".format(*out)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

"""Seasonal theme transforms — sakura / snow / matsuri / neon_night.

Plan: "季节风格不是独立 preset, 它是 `ThemeTransform`". The transform takes
a preset's `RenderScene` and a chosen theme, and returns a new scene whose
background / annotation colours suit the season. Reserved palette keys
(`unknown`, `no_data`, hazard ordering) are untouched.

The transforms are intentionally light — most of the visual change comes
from `style/theme.py` background / accent choices plus the renderer's
contrast knob. This module exists so the plan's "ThemeTransform" surface
has an explicit home and so future heavier transforms (paper grain,
overlays, hue shifts) can land here without changing the preset API.
"""

from __future__ import annotations

from dataclasses import replace

from prettyplateau.presets.scene import RenderScene
from prettyplateau.style.theme import Theme


def apply(scene: RenderScene, theme: Theme) -> RenderScene:
    """Return a possibly-modified scene with theme effects mixed in.

    The default behaviour is identity — the theme is consumed downstream by
    the renderer and composer. Future theme-specific spatial effects (e.g.
    snow scatter overlay on `snow`) land here. Reserved palette keys stay
    untouched in any future transform.
    """
    if theme.id in {"sakura", "summer_matsuri", "snow", "neon_night"}:
        return _apply_atmospheric(scene, theme)
    return scene


def _apply_atmospheric(scene: RenderScene, theme: Theme) -> RenderScene:
    """Soft transforms shared by the atmospheric themes.

    Currently restricted to nudging the scene background to the theme's
    chosen background so the scene-level background matches the figure
    background end-to-end. Heavier effects (paper texture, raster
    post-processing) live in `compose/composer.py` where they apply to the
    composed artifact after legend/title drawing.
    """
    if scene.background == theme.background:
        return scene
    return replace(scene, background=theme.background)

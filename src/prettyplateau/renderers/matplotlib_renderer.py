"""Matplotlib-based scene renderer.

The renderer is intentionally narrow: it converts a `RenderScene` into a
matplotlib `Figure`, and that's it. No file IO, no attribution logic, no
preset awareness. The Composer + AttributionInjector handle anything visible
to the user; this layer only handles geometry → pixels.

Design notes
------------

- Polygons are drawn through `PatchCollection` for speed. A naïve
  `ax.add_patch` loop over 100k buildings is ~30× slower.
- The figure is created in *inches* with explicit dpi so PNG/PDF/SVG all share
  a single pixel/point geometry, which keeps composer math sane.
- Equal-aspect is enforced after `set_xlim/ylim` so the city doesn't squash.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from prettyplateau.presets.scene import (
    ContourLayer,
    PolygonLayer,
    RenderScene,
)
from prettyplateau.style.theme import Theme

matplotlib.use("Agg", force=False)


@dataclass(frozen=True)
class RenderOptions:
    width_px: int = 3840
    height_px: int | None = None  # if None, infer from scene aspect
    dpi: int = 300
    background: str | None = None  # override theme.background when set
    margin: float = 0.02  # fraction of canvas reserved around the city
    # Composer reserves figure space for title/legend/attribution by shrinking
    # the main map axes. Values are figure-fraction (0..1).
    top_margin: float = 0.0
    bottom_margin: float = 0.0
    side_margin: float = 0.0


def _adjust_contrast(hex_color: str, theme: Theme) -> str:
    """Push a fill toward or away from theme.foreground based on theme.contrast.

    `contrast == 1.0`  → no change.
    `contrast > 1.0`   → mix toward foreground (more saturated/dark on light themes).
    `contrast < 1.0`   → mix toward background (washed out).
    The strength is bounded so even contrast=2.0 doesn't fully replace the colour.
    """
    c = hex_color.lstrip("#")
    r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
    blend_strength = max(min((theme.contrast - 1.0) * 0.35, 0.5), -0.5)
    target = theme.foreground if blend_strength > 0 else theme.background
    t = target.lstrip("#")
    tr, tg, tb = (int(t[i : i + 2], 16) for i in (0, 2, 4))
    a = abs(blend_strength)
    nr = int(r * (1 - a) + tr * a)
    ng = int(g * (1 - a) + tg * a)
    nb = int(b * (1 - a) + tb * a)
    return f"#{nr:02X}{ng:02X}{nb:02X}"


def _polygon_to_path(polygon: Polygon) -> MplPath:
    verts: list[tuple[float, float]] = []
    codes: list[int] = []

    def _add_ring(ring) -> None:
        coords = list(ring.coords)
        if not coords:
            return
        verts.extend(coords)
        codes.append(MplPath.MOVETO)
        codes.extend([MplPath.LINETO] * (len(coords) - 1))
        if coords[0] != coords[-1]:
            verts.append(coords[0])
            codes.append(MplPath.CLOSEPOLY)
        else:
            codes[-1] = MplPath.CLOSEPOLY

    _add_ring(polygon.exterior)
    for interior in polygon.interiors:
        _add_ring(interior)
    return MplPath(verts, codes)


def _geom_to_patches(geom: BaseGeometry) -> list[PathPatch]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [PathPatch(_polygon_to_path(geom))]
    if isinstance(geom, MultiPolygon):
        return [PathPatch(_polygon_to_path(p)) for p in geom.geoms]
    # Fall back: skip non-polygon geometries silently — preset chose this layer kind.
    return []


@dataclass
class PersistentRender:
    """Render output where geometry is materialised once and fills can be mutated.

    Used by the Animator to avoid rebuilding ~10⁵ matplotlib `PathPatch`
    objects every frame. The expensive geometry → patches step runs once;
    each subsequent frame is just `set_facecolors(...)` + canvas redraw,
    which is ~50× faster on Fukuoka-scale data.
    """

    figure: Figure
    # layer_id → matplotlib PatchCollection so the animator can swap fills.
    patch_collections: dict[str, PatchCollection]


class MatplotlibRenderer:
    def render(self, scene: RenderScene, theme: Theme, options: RenderOptions) -> Figure:
        minx, miny, maxx, maxy = scene.bounds
        dx = max(maxx - minx, 1e-9)
        dy = max(maxy - miny, 1e-9)

        width_px = options.width_px
        # Map axes will occupy [side, bottom, 1 - 2*side, 1 - top - bottom].
        side = max(options.side_margin, 0.0)
        top = max(options.top_margin, 0.0)
        bottom = max(options.bottom_margin, 0.0)
        ax_w = max(1.0 - 2 * side, 0.1)
        ax_h = max(1.0 - top - bottom, 0.1)

        if options.height_px is None:
            # Use latitude midpoint to get a reasonable aspect for unprojected coords.
            mid_lat = 0.5 * (miny + maxy)
            lat_correction = max(np.cos(np.deg2rad(mid_lat)), 0.1)
            data_aspect = dy / (dx * lat_correction)  # h/w of the city
            # Fit the city aspect into the available axes box. Figure height
            # must scale so that ax_h * H_fig / (ax_w * W_fig) == data_aspect.
            height_px = int(round(width_px * data_aspect * (ax_w / ax_h)))
            height_px = max(height_px, 256)
        else:
            height_px = options.height_px

        dpi = options.dpi
        fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
        fig.patch.set_facecolor(options.background or scene.background or theme.background)
        ax = fig.add_axes((side, bottom, ax_w, ax_h))
        ax.set_facecolor(options.background or scene.background or theme.background)
        ax.set_axis_off()

        # Equal aspect respecting latitude (lon spacing shrinks with cos lat).
        mid_lat = 0.5 * (miny + maxy)
        lat_correction = max(np.cos(np.deg2rad(mid_lat)), 0.1)
        ax.set_aspect(1.0 / lat_correction)

        margin_x = dx * options.margin
        margin_y = dy * options.margin
        ax.set_xlim(minx - margin_x, maxx + margin_x)
        ax.set_ylim(miny - margin_y, maxy + margin_y)

        ordered = sorted(scene.layers, key=lambda L: L.z)
        for layer in ordered:
            if isinstance(layer, PolygonLayer):
                self._draw_polygon_layer(ax, layer, theme)
            elif isinstance(layer, ContourLayer):
                self._draw_contour_layer(ax, layer)
        return fig

    def render_persistent(
        self,
        scene: RenderScene,
        theme: Theme,
        options: RenderOptions,
    ) -> PersistentRender:
        """Render once and return handles to the PatchCollections.

        Same visual output as `render()`; differs only in that the caller can
        later mutate fills via `update_layer_fills`. Use this for animations.
        """
        fig = self.render(scene, theme, options)
        # Find PatchCollections we just added. Match by per-axes traversal
        # because we tagged them with layer id in `_draw_polygon_layer`.
        collections: dict[str, PatchCollection] = {}
        for ax in fig.axes:
            for child in ax.collections:
                if isinstance(child, PatchCollection):
                    label = child.get_label() or ""
                    if label:
                        collections[label] = child
        return PersistentRender(figure=fig, patch_collections=collections)

    @staticmethod
    def update_layer_fills(persistent: PersistentRender, layer_id: str, fills: list[str]) -> None:
        """Swap the facecolor array on a layer's PatchCollection.

        `fills` must align with the original geometry order. MultiPolygons in
        the source scene expand to multiple patches, so we expand fills the
        same way using the cached patch counts.
        """
        pc = persistent.patch_collections.get(layer_id)
        if pc is None:
            return
        # Each PatchCollection caches the per-geometry patch counts as a
        # private attribute we set in `_draw_polygon_layer`.
        per_geom = getattr(pc, "_prettyplateau_per_geom_counts", None)
        if per_geom is None or len(per_geom) != len(fills):
            pc.set_facecolors(fills)
            return
        expanded: list[str] = []
        for count, fill in zip(per_geom, fills, strict=False):
            expanded.extend([fill] * count)
        pc.set_facecolors(expanded)

    def _draw_polygon_layer(self, ax, layer: PolygonLayer, theme: Theme) -> None:
        if not layer.geometries:
            return
        patches: list[PathPatch] = []
        colors: list[str] = []
        per_geom_counts: list[int] = []
        # Apply the theme's global contrast knob, but RESPECT reserved
        # palette keys. If the preset tagged each fill with its source key
        # (PolygonLayer.fill_keys), we look those up against RESERVED_KEYS
        # and leave them untouched — that keeps `unknown` grey, no-data
        # hatching, and hazard severity bands semantically stable across
        # themes, even when contrast != 1.0.
        from prettyplateau.style.palette import RESERVED_KEYS

        if abs(theme.contrast - 1.0) > 1e-3:
            keys = layer.fill_keys or [""] * len(layer.fills)
            colors = [
                c if k in RESERVED_KEYS else _adjust_contrast(c, theme)
                for c, k in zip(layer.fills, keys, strict=False)
            ]
        else:
            colors = list(layer.fills)
        for geom in layer.geometries:
            geom_patches = _geom_to_patches(geom)
            per_geom_counts.append(len(geom_patches))
            patches.extend(geom_patches)
        # Re-expand colors to match per-geom patch counts.
        expanded_colors: list[str] = []
        for count, color in zip(per_geom_counts, colors, strict=False):
            expanded_colors.extend([color] * count)
        colors = expanded_colors
        if not patches:
            return
        collection = PatchCollection(
            patches,
            match_original=False,
            linewidths=layer.edge_width * theme.line_width_scale,
            edgecolors=layer.edge_color if layer.edge_color else "none",
            facecolors=colors,
            antialiased=True,
        )
        collection.set_alpha(layer.alpha)
        collection.set_label(layer.id)
        # Stash the geometry-count map so the animator can re-expand fills
        # without recomputing patch counts.
        collection._prettyplateau_per_geom_counts = per_geom_counts  # type: ignore[attr-defined]
        ax.add_collection(collection)

    def _draw_contour_layer(self, ax, layer: ContourLayer) -> None:
        # Stub for height_topo etc; v1 keeps it minimal.
        if layer.points_xy.size == 0:
            return
        # No contour engine wired up in v1 — preset would render polygons instead.

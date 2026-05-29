"""RenderScene — the data structure that flows from preset to renderer.

The renderer must be able to draw a scene without knowing which preset built it
or which city it represents. Anything semantic (legend label, unknown bucket,
risk ordering) is encoded into the scene; the renderer only chooses how to
paint geometry given style.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from shapely.geometry.base import BaseGeometry

LayerKind = Literal["polygon", "line", "point", "raster", "text", "contour"]


@dataclass(frozen=True)
class PolygonLayer:
    """Many polygons sharing the same draw config but possibly different fills.

    `geometries` and `fills` must be the same length. `edge_color` and
    `edge_width` are constant per layer; per-polygon edge styling needs its own
    layer (kept simple to keep the matplotlib PatchCollection fast path).
    """

    id: str
    kind: Literal["polygon"] = "polygon"
    geometries: list[BaseGeometry] = field(default_factory=list)
    fills: list[str] = field(default_factory=list)
    # Parallel to `fills`: the palette key each fill came from. Used by the
    # renderer to know which fills are reserved-semantic (`unknown`, `no_data`,
    # hazard-ordering keys) so theme `contrast` transforms don't recolour
    # them. Empty list disables this protection (legacy code path).
    fill_keys: list[str] = field(default_factory=list)
    edge_color: str | None = None
    edge_width: float = 0.0
    alpha: float = 1.0
    z: int = 0
    semantic: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.geometries) != len(self.fills):
            raise ValueError(
                f"PolygonLayer {self.id!r}: geometries ({len(self.geometries)}) "
                f"and fills ({len(self.fills)}) must have equal length"
            )
        if self.fill_keys and len(self.fill_keys) != len(self.fills):
            raise ValueError(
                f"PolygonLayer {self.id!r}: fill_keys ({len(self.fill_keys)}) "
                f"must match fills ({len(self.fills)}) when supplied"
            )


@dataclass(frozen=True)
class ContourLayer:
    """Heightmap / topo contour lines."""

    id: str
    kind: Literal["contour"] = "contour"
    points_xy: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    values: np.ndarray = field(default_factory=lambda: np.zeros(0))
    levels: tuple[float, ...] = ()
    line_color: str = "#111111"
    line_width: float = 0.6
    alpha: float = 0.7
    z: int = 0
    semantic: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextAnnotation:
    text: str
    x: float
    y: float
    align: Literal["left", "center", "right"] = "left"
    valign: Literal["top", "center", "bottom"] = "bottom"
    color: str = "#111111"
    size: float = 9.0
    weight: Literal["regular", "medium", "bold"] = "regular"
    rotation: float = 0.0
    z: int = 1000


@dataclass(frozen=True)
class LegendEntry:
    label: str
    color: str
    swatch: Literal["square", "circle", "hash"] = "square"
    is_no_data: bool = False


@dataclass(frozen=True)
class LegendSpec:
    title: str
    entries: tuple[LegendEntry, ...]
    note: str | None = None  # e.g. "No data: this dataset does not cover this hazard"


@dataclass(frozen=True)
class RenderScene:
    """Output of `Preset.build_scene`. Pure data; no matplotlib objects."""

    bounds: tuple[float, float, float, float]  # (minx, miny, maxx, maxy) in EPSG:4326
    background: str
    layers: tuple[PolygonLayer | ContourLayer, ...]
    legend: LegendSpec | None = None
    annotations: tuple[TextAnnotation, ...] = ()
    semantic_metadata: dict[str, Any] = field(default_factory=dict)

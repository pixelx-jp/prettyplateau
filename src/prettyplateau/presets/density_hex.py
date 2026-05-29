"""Density Hex — building count aggregated onto a hex grid.

Unlike the other presets which colour individual building polygons, this one
projects the centroids onto a hexagonal lattice and colours each cell by log-
binned count. The visual goal: see Tokyo's stations / commercial spines /
machiya districts as bright bands without being distracted by individual
buildings.

We use a flat-top hex layout in lon/lat space, latitude-corrected so cells
look roughly hexagonal at the equator-to-pole spectrum we care about.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.presets._common import bbox_of_gdf
from prettyplateau.presets._layers import admin_boundary_layer
from prettyplateau.presets.base import BasePreset, PreparedData
from prettyplateau.presets.scene import (
    LegendEntry,
    LegendSpec,
    PolygonLayer,
    RenderScene,
)
from prettyplateau.style.palette import apply_theme_overrides, load_palette
from prettyplateau.style.theme import Theme


_BUCKETS = ("d0", "d1", "d2", "d3", "d4", "d5", "d6")


def _make_hex(cx: float, cy: float, radius_lon: float, radius_lat: float) -> Polygon:
    """Flat-top hexagon centred at (cx, cy)."""
    pts = []
    for i in range(6):
        a = math.radians(60 * i)
        pts.append((cx + radius_lon * math.cos(a), cy + radius_lat * math.sin(a)))
    return Polygon(pts)


def _hex_grid(
    bbox: tuple[float, float, float, float],
    cell_km: float,
    points_lon: np.ndarray,
    points_lat: np.ndarray,
) -> tuple[list[Polygon], np.ndarray]:
    """Return hex polygons + counts for cells that contain at least one point."""
    minx, miny, maxx, maxy = bbox
    mid_lat = 0.5 * (miny + maxy)
    # 1° latitude ≈ 111.32 km; longitude shrinks with cos(lat).
    deg_per_km_lat = 1.0 / 111.32
    deg_per_km_lon = deg_per_km_lat / max(math.cos(math.radians(mid_lat)), 0.1)
    radius_lon = cell_km * deg_per_km_lon
    radius_lat = cell_km * deg_per_km_lat
    # Flat-top hex: horizontal spacing = 1.5 * R, vertical = sqrt(3) * R.
    step_x = 1.5 * radius_lon
    step_y = math.sqrt(3) * radius_lat

    # Snap point coordinates to nearest hex centre. For flat-top hex layout we
    # use the axial coordinate inverse — approximate, but plenty accurate for
    # binning at the scales we render (≥0.2 km).
    rel_x = (points_lon - minx) / step_x
    col = np.round(rel_x).astype(int)
    row_offset = (col & 1) * 0.5 * step_y
    rel_y = (points_lat - miny - row_offset) / step_y
    row = np.round(rel_y).astype(int)
    keys = pd.MultiIndex.from_arrays([col, row], names=("col", "row"))
    counts = pd.Series(1, index=keys).groupby(level=("col", "row")).sum()

    polys: list[Polygon] = []
    out_counts: list[int] = []
    for (c, r), n in counts.items():
        cx = minx + c * step_x
        cy = miny + r * step_y + (c & 1) * 0.5 * step_y
        polys.append(_make_hex(cx, cy, radius_lon, radius_lat))
        out_counts.append(int(n))
    return polys, np.array(out_counts)


def _bucket_counts(counts: np.ndarray) -> list[str]:
    # Log-binned buckets so a handful of dense hexes don't compress the rest.
    if counts.size == 0:
        return []
    logs = np.log1p(counts)
    lo, hi = float(logs.min()), float(logs.max())
    if hi <= lo:
        return ["d3"] * counts.size
    norm = (logs - lo) / (hi - lo)
    idx = np.clip((norm * len(_BUCKETS)).astype(int), 0, len(_BUCKETS) - 1)
    return [_BUCKETS[i] for i in idx]


class DensityHexPreset(BasePreset):
    metadata = PresetMetadata(
        id="density_hex",
        name="Density Hex",
        description="Building-count aggregation onto a hex lattice. Reveals stations and commercial spines.",
        modes=["static"],
        required_fields=["centroid_lon", "centroid_lat"],
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        cell_km = float(request.options.get("cell_km", 0.25))
        bbox = bbox_of_gdf(gdf)
        lon = pd.to_numeric(gdf["centroid_lon"], errors="coerce").to_numpy(dtype=float)
        lat = pd.to_numeric(gdf["centroid_lat"], errors="coerce").to_numpy(dtype=float)
        mask = ~np.isnan(lon) & ~np.isnan(lat)
        polys, counts = _hex_grid(bbox, cell_km, lon[mask], lat[mask])
        return PreparedData(
            dataset=dataset,
            derived={"hex_polys": polys, "hex_counts": counts, "cell_km": cell_km},
        )

    def build_scene(self, prepared: PreparedData, theme: Theme, request: RenderRequest) -> RenderScene:
        ds = prepared.dataset
        polys = prepared.derived["hex_polys"]
        counts = prepared.derived["hex_counts"]
        cell_km = prepared.derived["cell_km"]
        palette = apply_theme_overrides(load_palette("density_hex"), theme)
        bucket_keys = _bucket_counts(counts)
        fills = [palette.color_for(k) for k in bucket_keys]

        layer = PolygonLayer(
            id="hexes",
            geometries=polys,
            fills=fills,
            fill_keys=list(bucket_keys),
            edge_color=theme.background,
            edge_width=0.15,
            alpha=0.95,
            z=10,
            semantic={"field": "density_hex", "cell_km": cell_km},
        )
        # Show a meaningful legend even though counts are continuous: anchor
        # each bucket label to its current count range.
        if counts.size:
            sorted_keys = sorted({k for k in bucket_keys})
            count_by_bucket = {
                k: counts[[bk == k for bk in bucket_keys]] for k in sorted_keys
            }
            entries = tuple(
                LegendEntry(
                    label=f"{int(count_by_bucket[k].min())}–{int(count_by_bucket[k].max())} bldgs/cell",
                    color=palette.color_for(k),
                )
                for k in _BUCKETS
                if k in count_by_bucket
            )
        else:
            entries = tuple(LegendEntry(label=k, color=palette.color_for(k)) for k in _BUCKETS)
        legend = LegendSpec(
            title=f"Buildings per {cell_km:.2f} km hex",
            entries=entries,
        )
        boundary = admin_boundary_layer(ds, theme)
        layers = (boundary, layer) if boundary else (layer,)
        return RenderScene(
            bounds=bbox_of_gdf(ds.gdf),
            background=theme.background,
            layers=layers,
            legend=legend,
            semantic_metadata={
                "preset": self.metadata.id,
                "n_buildings": int(len(ds.gdf)),
                "n_hexes": int(len(polys)),
                "cell_km": cell_km,
            },
        )


PRESET = DensityHexPreset()


def factory() -> DensityHexPreset:
    return DensityHexPreset()

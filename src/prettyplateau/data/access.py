"""DataAccess — anti-corruption layer over plateau-core / _core_lite.

Presets must never import `plateau_bridge` or `prettyplateau._core_lite` directly;
they go through `DataAccess` so we can swap backends without touching presets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from prettyplateau._core_lite import discover_city
from prettyplateau._core_lite import load_buildings as _lite_load_buildings
from prettyplateau._core_lite import load_manifest as _lite_load_manifest
from prettyplateau.core.logging import get_logger
from prettyplateau.data import core_adapter

_logger = get_logger("data")


def _resolve_admin_geojson() -> Path | None:
    """Locate plateau_bridge's bundled administrative-boundary geojson.

    plateau-bridge ships `data/japan_admin.geojson` keyed by the JIS city_code.
    We use it (when available) to draw the city silhouette underneath the
    buildings layer. The lookup is best-effort: if the file isn't present —
    e.g. offline mode without plateau_bridge installed — boundaries are
    simply omitted and the rest of the pipeline still works.
    """
    try:
        from importlib.resources import files

        target = files("plateau_bridge.data") / "japan_admin.geojson"
        p = Path(str(target))
        if p.is_file():
            return p
    except Exception:  # noqa: BLE001 — purely a discovery helper
        pass
    # Editable-install fallback: scan a couple of parents for the sibling repo.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "plateau-core" / "src" / "plateau_bridge" / "data" / "japan_admin.geojson"
        if candidate.is_file():
            return candidate
        candidate = parent / "src" / "plateau_bridge" / "data" / "japan_admin.geojson"
        if candidate.is_file():
            return candidate
    return None


_ADMIN_CACHE: dict[str, BaseGeometry] = {}


def lookup_admin_boundary(city_code: str) -> BaseGeometry | None:
    """Return a (possibly multi-) polygon outlining the given JIS city_code, or None."""
    if not city_code:
        return None
    if city_code in _ADMIN_CACHE:
        return _ADMIN_CACHE[city_code]
    geojson_path = _resolve_admin_geojson()
    if geojson_path is None:
        return None
    try:
        gdf = gpd.read_file(geojson_path)
    except Exception:  # noqa: BLE001
        return None
    # The geojson uses several different code columns; match against both.
    code_col = "city_code" if "city_code" in gdf.columns else "code"
    rows = gdf[gdf[code_col].astype(str) == str(city_code)]
    if rows.empty and "parent_city_code" in gdf.columns:
        rows = gdf[gdf["parent_city_code"].astype(str) == str(city_code)]
    if rows.empty:
        return None
    # Dissolve to a single boundary so consumers don't worry about ward splits.
    # `unary_union` can choke on slightly-invalid geometries (PLATEAU has a few
    # boundary polygons where a hole isn't fully enclosed by its shell). When
    # that happens we fall back to a pre-cleaning step via buffer(0); if that
    # still fails the boundary is dropped — the city renders without a
    # silhouette, which is preferable to crashing the whole pipeline.
    try:
        boundary: BaseGeometry = rows.geometry.unary_union
    except Exception:  # noqa: BLE001 — topology exceptions vary by shapely version
        try:
            cleaned = rows.geometry.buffer(0)
            boundary = cleaned.unary_union
        except Exception:  # noqa: BLE001
            _ADMIN_CACHE[city_code] = None  # type: ignore[assignment]
            return None
    _ADMIN_CACHE[city_code] = boundary
    return boundary


@dataclass(frozen=True)
class CityDataset:
    """Public dataset shape that presets consume."""

    city: str
    city_name: str
    city_code: str
    dataset_year: int | None
    dataset_id: str | None
    attribution: str
    field_coverage: dict[str, float] = field(default_factory=dict)
    n_buildings: int = 0
    gdf: gpd.GeoDataFrame = field(default_factory=gpd.GeoDataFrame)
    source_root: Path | None = None
    admin_boundary: BaseGeometry | None = None  # set by DataAccess when discoverable
    extras: dict[str, Any] = field(default_factory=dict)


class DataAccess:
    """Default implementation backed by `_core_lite`.

    Week 4 switch: replace `load_city` with a thin wrapper over plateau-core's
    public API; the public surface here doesn't change.
    """

    def __init__(
        self,
        data_root: str | os.PathLike[str] | None = None,
        *,
        prefer_core: bool | None = None,
    ) -> None:
        """`prefer_core`: True forces plateau_bridge, False forces _core_lite.
        None (default) auto-selects: use plateau_bridge when importable."""
        self._data_root = data_root
        if prefer_core is None:
            prefer_core = core_adapter.is_available()
        self._prefer_core = prefer_core
        _logger.info("DataAccess backend = %s", "plateau_bridge" if prefer_core else "core_lite")

    def load_city(
        self,
        city: str,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        columns: list[str] | None = None,
    ) -> CityDataset:
        root = discover_city(city, self._data_root)
        if self._prefer_core:
            cmf = core_adapter.load_manifest(root)
            gdf = core_adapter.load_buildings(root, columns=columns, bbox=bbox)
            return CityDataset(
                city=city,
                city_name=cmf.city_name,
                city_code=cmf.city_code,
                dataset_year=cmf.dataset_year,
                dataset_id=cmf.primary_dataset_id,
                attribution=cmf.attribution,
                field_coverage=cmf.field_coverage,
                n_buildings=cmf.n_buildings,
                gdf=gdf,
                source_root=root,
                admin_boundary=lookup_admin_boundary(cmf.city_code),
                extras={"raw_manifest": cmf.raw, "backend": "plateau_bridge"},
            )
        manifest = _lite_load_manifest(root)
        gdf = _lite_load_buildings(root, columns=columns, bbox=bbox)
        return CityDataset(
            city=city,
            city_name=manifest.city_name,
            city_code=manifest.city_code,
            dataset_year=manifest.dataset_year,
            dataset_id=manifest.primary_dataset_id,
            attribution=manifest.attribution,
            field_coverage=manifest.field_coverage,
            n_buildings=manifest.n_buildings,
            gdf=gdf,
            source_root=root,
            admin_boundary=lookup_admin_boundary(manifest.city_code),
            extras={"raw_manifest": manifest.raw, "backend": "core_lite"},
        )

    def get_attribution(self, dataset: CityDataset) -> str:
        return dataset.attribution

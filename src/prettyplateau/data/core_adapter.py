"""Adapter over the real `plateau_bridge` public API.

This was the Week 4 swap-in for the embedded `_core_lite` reader. Both
implement the same `read_dataset(root)` contract; `DataAccess` chooses the
adapter at construction time. Keeping both lets prettyplateau work in two
modes:

  - **library mode** (default): plateau_bridge installed, use canonical
    `Manifest` parsing and the published Arrow schema constants.
  - **offline mode**: only the parquet directory is available (e.g. CI
    without the plateau_bridge wheel). Falls back to `_core_lite`.

The adapter narrows the dependency surface to two symbols: `Manifest` (for
typed metadata) and the column names in `schema.BUILDINGS_ARROW_SCHEMA`.
Anything else stays inside this module so presets remain insulated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq
import shapely.wkb as _wkb

from prettyplateau.core.errors import DataNotFoundError
from prettyplateau.core.logging import get_logger

_logger = get_logger("core_adapter")


@dataclass(frozen=True)
class CoreManifest:
    """Read-only view over plateau_bridge.Manifest with the fields we use.

    Re-projected to a small dataclass so `data/access.py` can stay generic.
    """

    raw: object  # `plateau_bridge.Manifest`
    city_name: str
    city_code: str
    dataset_year: int | None
    attribution: str
    n_buildings: int
    datasets: list[str]
    primary_dataset_id: str | None
    field_coverage: dict[str, float]


def _coerce_primary_dataset_id(datasets: list[str]) -> str | None:
    for d in datasets:
        if "-bldg" in d:
            return d
    return datasets[0] if datasets else None


def is_available() -> bool:
    try:
        import plateau_bridge  # noqa: F401

        return True
    except ImportError:
        return False


def load_manifest(root: Path) -> CoreManifest:
    """Parse manifest.json via plateau_bridge.Manifest's pydantic validator."""
    try:
        from plateau_bridge import Manifest
    except ImportError as exc:  # pragma: no cover — handled by DataAccess
        raise DataNotFoundError("plateau_bridge is not installed") from exc

    p = root / "manifest.json"
    if not p.is_file():
        raise DataNotFoundError(f"manifest.json missing under {root}")
    text = p.read_text(encoding="utf-8")
    manifest = Manifest.model_validate_json(text)
    datasets = list(manifest.datasets)
    return CoreManifest(
        raw=manifest,
        city_name=manifest.city_name,
        city_code=manifest.city_code,
        dataset_year=int(manifest.dataset_year) if manifest.dataset_year is not None else None,
        attribution=manifest.attribution,
        n_buildings=int(manifest.n_buildings),
        datasets=datasets,
        primary_dataset_id=_coerce_primary_dataset_id(datasets),
        field_coverage=dict(manifest.field_coverage or {}),
    )


def load_buildings(
    root: Path,
    columns: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> gpd.GeoDataFrame:
    """Same contract as `_core_lite.load_buildings`.

    Uses `BUILDINGS_ARROW_SCHEMA` from plateau_bridge to validate the requested
    columns when supplied (catches typos at the API boundary, not deep inside
    a preset).
    """
    try:
        from plateau_bridge.schema import BUILDINGS_ARROW_SCHEMA
    except ImportError as exc:
        raise DataNotFoundError("plateau_bridge is not installed") from exc

    pq_path = root / "buildings.parquet"
    if not pq_path.is_file():
        raise DataNotFoundError(f"buildings.parquet missing under {root}")

    if columns is not None:
        known = set(BUILDINGS_ARROW_SCHEMA.names)
        unknown = [c for c in columns if c not in known]
        if unknown:
            _logger.warning(
                "requested columns not present in plateau_bridge schema: %s", unknown
            )
        cols = list({*columns, "geometry", "centroid_lon", "centroid_lat"})
    else:
        cols = None

    table = pq.read_table(pq_path, columns=cols)
    df = table.to_pandas()
    _logger.info("loaded %d rows from %s via plateau_bridge adapter", len(df), pq_path)

    if bbox is not None and {"centroid_lon", "centroid_lat"}.issubset(df.columns):
        minx, miny, maxx, maxy = bbox
        m = (
            (df["centroid_lon"] >= minx)
            & (df["centroid_lon"] <= maxx)
            & (df["centroid_lat"] >= miny)
            & (df["centroid_lat"] <= maxy)
        )
        df = df[m].reset_index(drop=True)

    geom = df["geometry"].map(lambda b: _wkb.loads(b) if b is not None else None)
    gdf = gpd.GeoDataFrame(df.drop(columns=["geometry"]), geometry=geom, crs="EPSG:4326")
    return gdf

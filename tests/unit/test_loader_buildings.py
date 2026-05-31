"""Direct tests for `_core_lite.load_buildings`.

The rest of the suite stubs out `DataAccess`, so the real loader — vectorized
WKB decode, column projection against the file schema, and the centroid bbox
prefilter — has no other coverage. These tests build a tiny WKB parquet matching
the plateau-bridge layout and exercise the loader end to end.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import shapely
from shapely.geometry import Point

from prettyplateau._core_lite.loader import load_buildings


def _write_parquet(root: Path, n: int = 5) -> Path:
    # Buildings on a diagonal so the centroid bbox prefilter is easy to reason
    # about: building i sits at lon=i, lat=i.
    geoms = [Point(i, i).buffer(0.1) for i in range(n)]
    table = pa.table(
        {
            "building_uid": [f"b{i}" for i in range(n)],
            "geometry": [shapely.to_wkb(g) for g in geoms],
            "centroid_lon": [float(i) for i in range(n)],
            "centroid_lat": [float(i) for i in range(n)],
            "height": [10.0 + i for i in range(n)],
            "year_built": [1980 + i for i in range(n)],
        }
    )
    pq.write_table(table, root / "buildings.parquet")
    return root


def test_decodes_wkb_geometry(tmp_path: Path) -> None:
    root = _write_parquet(tmp_path)
    gdf = load_buildings(root)
    assert len(gdf) == 5
    assert str(gdf.crs).upper() == "EPSG:4326"
    # Geometry column is real shapely polygons, not raw WKB bytes.
    assert gdf.geometry.geom_type.eq("Polygon").all()
    assert not gdf.geometry.is_empty.any()


def test_column_projection_only_loads_requested_plus_geometry(tmp_path: Path) -> None:
    root = _write_parquet(tmp_path)
    gdf = load_buildings(root, columns=["height"])
    # Requested column + always-added geometry/centroid; year_built is dropped.
    assert "height" in gdf.columns
    assert "year_built" not in gdf.columns
    assert "geometry" in gdf.columns
    assert {"centroid_lon", "centroid_lat"}.issubset(gdf.columns)


def test_requesting_absent_column_does_not_raise(tmp_path: Path) -> None:
    root = _write_parquet(tmp_path)
    # A column the preset wants but the parquet lacks must be silently skipped
    # (the schema intersection), not raise inside read_table.
    gdf = load_buildings(root, columns=["height", "does_not_exist"])
    assert "height" in gdf.columns
    assert "does_not_exist" not in gdf.columns
    assert len(gdf) == 5


def test_bbox_prefilter_keeps_only_buildings_inside(tmp_path: Path) -> None:
    root = _write_parquet(tmp_path)
    # Centroids are at (0,0),(1,1),...,(4,4). Box around 1..2 keeps b1 and b2.
    gdf = load_buildings(root, bbox=(0.5, 0.5, 2.5, 2.5))
    assert sorted(gdf["building_uid"]) == ["b1", "b2"]


def test_empty_bbox_yields_empty_frame(tmp_path: Path) -> None:
    root = _write_parquet(tmp_path)
    gdf = load_buildings(root, bbox=(100.0, 100.0, 101.0, 101.0))
    assert len(gdf) == 0
    # Still a usable GeoDataFrame with a geometry column.
    assert "geometry" in gdf.columns


def test_missing_parquet_raises(tmp_path: Path) -> None:
    from prettyplateau.core.errors import DataNotFoundError

    with pytest.raises(DataNotFoundError):
        load_buildings(tmp_path)

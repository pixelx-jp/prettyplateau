"""Read `buildings.parquet` + `manifest.json` from a plateau-bridge output dir."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import pyarrow.parquet as pq
import shapely.wkb as _wkb

from prettyplateau.core.errors import DataNotFoundError
from prettyplateau.core.logging import get_logger

_logger = get_logger("core_lite")


# Slug -> directory-name candidates. Adding aliases here is enough; users can
# also pass an explicit `data_root` (absolute path to an out_* directory).
CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "shibuya": ("shibuya", "shibuya-ku", "渋谷"),
    "shinjuku": ("shinjuku", "shinjuku-ku"),
    "minato": ("minato", "minato-ku"),
    "chiyoda": ("chiyoda", "chiyoda-ku"),
    "chuo": ("chuo", "chuo-ku"),
    "setagaya": ("setagaya", "setagaya-ku"),
    "meguro": ("meguro", "meguro-ku"),
    "shinagawa": ("shinagawa", "shinagawa-ku"),
    "ota": ("ota", "ota-ku"),
    "suginami": ("suginami", "suginami-ku"),
    "nakano": ("nakano", "nakano-ku"),
    "toshima": ("toshima", "toshima-ku"),
    "nerima": ("nerima", "nerima-ku"),
    "itabashi": ("itabashi", "itabashi-ku"),
    "kita": ("kita", "kita-ku"),
    "arakawa": ("arakawa", "arakawa-ku"),
    "adachi": ("adachi", "adachi-ku"),
    "katsushika": ("katsushika", "katsushika-ku"),
    "edogawa": ("edogawa", "edogawa-ku"),
    "sumida": ("sumida", "sumida-ku"),
    "koto": ("koto", "koto-ku"),
    "taito": ("taito", "taito-ku"),
    "bunkyo": ("bunkyo", "bunkyo-ku"),
    "yokohama": ("yokohama",),
    "kamakura": ("kamakura",),
    "nagoya": ("nagoya",),
    "osaka": ("osaka",),
    "fukuoka": ("fukuoka",),
    "sapporo": ("sapporo",),
}


@dataclass(frozen=True)
class LiteManifest:
    raw: dict[str, Any]

    @property
    def city_name(self) -> str:
        return self.raw.get("city_name", "")

    @property
    def city_code(self) -> str:
        return self.raw.get("city_code", "")

    @property
    def dataset_year(self) -> int | None:
        v = self.raw.get("dataset_year")
        return int(v) if v is not None else None

    @property
    def attribution(self) -> str:
        return self.raw.get("attribution", "© Project PLATEAU / MLIT (CC BY 4.0)")

    @property
    def n_buildings(self) -> int:
        return int(self.raw.get("n_buildings", 0))

    @property
    def datasets(self) -> list[str]:
        return list(self.raw.get("datasets", []))

    @property
    def primary_dataset_id(self) -> str | None:
        for d in self.datasets:
            if "-bldg" in d:
                return d
        return self.datasets[0] if self.datasets else None

    @property
    def field_coverage(self) -> dict[str, float]:
        return dict(self.raw.get("field_coverage", {}))


@dataclass(frozen=True)
class LiteCityDataset:
    city_slug: str
    root: Path
    manifest: LiteManifest
    gdf: gpd.GeoDataFrame


def _candidate_roots(explicit: str | os.PathLike[str] | None) -> list[Path]:
    if explicit:
        return [Path(explicit).expanduser().resolve()]
    env = os.environ.get("PRETTYPLATEAU_DATA_ROOT")
    roots: list[Path] = []
    if env:
        roots.append(Path(env).expanduser().resolve())
    # Sibling plateau-core checkout — the common dev layout.
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "plateau-core"
        if cand.is_dir():
            roots.append(cand)
            break
    # Current working directory.
    roots.append(Path.cwd())
    return roots


def discover_city(city: str, data_root: str | os.PathLike[str] | None = None) -> Path:
    """Locate the `out_<slug>` directory for a city. Returns its absolute path.

    Search order:
      1. If `city` is itself a path to a directory containing `buildings.parquet`,
         use it directly.
      2. `data_root` argument.
      3. `PRETTYPLATEAU_DATA_ROOT` env var.
      4. Sibling `plateau-core/` checkout.
      5. CWD.
    """
    # 1. direct path
    p = Path(city).expanduser()
    if p.is_dir() and (p / "buildings.parquet").is_file():
        return p.resolve()

    slug = city.lower().strip()
    candidates = CITY_ALIASES.get(slug, (slug,))

    for root in _candidate_roots(data_root):
        for cand in candidates:
            for name in (f"out_{cand}", cand, f"out_{cand}-ku"):
                d = root / name
                if d.is_dir() and (d / "buildings.parquet").is_file():
                    return d.resolve()

    raise DataNotFoundError(
        f"could not locate buildings.parquet for city {city!r}. "
        f"Pass --data-root or set PRETTYPLATEAU_DATA_ROOT to a directory "
        f"containing out_<city>/buildings.parquet."
    )


def load_manifest(root: Path) -> LiteManifest:
    p = root / "manifest.json"
    if not p.is_file():
        raise DataNotFoundError(f"manifest.json missing under {root}")
    return LiteManifest(raw=json.loads(p.read_text(encoding="utf-8")))


def load_buildings(
    root: Path,
    columns: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> gpd.GeoDataFrame:
    """Load buildings.parquet into a GeoDataFrame in EPSG:4326.

    The parquet file uses WKB for the geometry column rather than the GeoParquet
    convention, so we decode it manually with shapely. `bbox` filtering happens
    after load — pyarrow predicate pushdown on WKB blobs isn't useful here.
    """
    pq_path = root / "buildings.parquet"
    if not pq_path.is_file():
        raise DataNotFoundError(f"buildings.parquet missing under {root}")

    cols = None
    if columns is not None:
        # Always need geometry + the centroid for bbox prefilter.
        cols = list({*columns, "geometry", "centroid_lon", "centroid_lat"})
    table = pq.read_table(pq_path, columns=cols)
    df = table.to_pandas()
    _logger.info("loaded %d rows from %s", len(df), pq_path)

    if bbox is not None and {"centroid_lon", "centroid_lat"}.issubset(df.columns):
        minx, miny, maxx, maxy = bbox
        m = (
            (df["centroid_lon"] >= minx)
            & (df["centroid_lon"] <= maxx)
            & (df["centroid_lat"] >= miny)
            & (df["centroid_lat"] <= maxy)
        )
        df = df[m].reset_index(drop=True)
        _logger.info("after bbox filter: %d rows", len(df))

    geom = df["geometry"].map(lambda b: _wkb.loads(b) if b is not None else None)
    gdf = gpd.GeoDataFrame(df.drop(columns=["geometry"]), geometry=geom, crs="EPSG:4326")
    return gdf

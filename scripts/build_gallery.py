"""Render the multi-city launch gallery.

Each row in `MATRIX` says "render preset X on city Y". The script:
  - skips entries whose required field has zero coverage (no point rendering
    a 100% grey canvas as a launch sample);
  - downsamples mega-cities at composition time via `--width 1800` so the run
    fits in a reasonable wall-clock budget;
  - writes a manifest of what was produced so README/Twitter copy can be
    generated from it programmatically.

Run:
  python scripts/build_gallery.py --data-root ../plateau-core --out gallery
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from prettyplateau.api.render import render
from prettyplateau.data.access import DataAccess


@dataclass(frozen=True)
class GallerySpec:
    city: str
    preset: str
    title: str
    subtitle: str
    width: int = 2400
    theme: str = "default"


MATRIX: tuple[GallerySpec, ...] = (
    # use_mosaic — works on every city, anchor of the gallery.
    GallerySpec("shibuya", "use_mosaic", "Shibuya — Use Mosaic", "Per-building usage · PLATEAU 2023"),
    GallerySpec("minato", "use_mosaic", "Minato — Use Mosaic", "Per-building usage · PLATEAU 2023"),
    GallerySpec("shinjuku", "use_mosaic", "Shinjuku — Use Mosaic", "Per-building usage · PLATEAU 2023"),
    GallerySpec("osaka", "use_mosaic", "Osaka — Use Mosaic", "Per-building usage · PLATEAU 2024", width=1800),
    GallerySpec("kamakura", "use_mosaic", "Kamakura — Use Mosaic", "Per-building usage · PLATEAU"),

    # height_topo — best on Tokyo high-rise wards.
    GallerySpec("minato", "height_topo", "Minato — Height Topo", "Building height as topo · PLATEAU 2023"),
    GallerySpec("shinjuku", "height_topo", "Shinjuku — Height Topo", "Building height as topo · PLATEAU 2023"),
    GallerySpec("chiyoda", "height_topo", "Chiyoda — Height Topo", "Building height as topo · PLATEAU 2023"),

    # flood_depth — simple per-building river-flood depth choropleth.
    GallerySpec("shibuya", "flood_depth", "Shibuya — Flood Depth", "Per-building flood depth · PLATEAU 2023"),
    GallerySpec("koto", "flood_depth", "Kōtō — Flood Depth", "Per-building flood depth · PLATEAU 2023"),
    GallerySpec("edogawa", "flood_depth", "Edogawa — Flood Depth", "Per-building flood depth · PLATEAU 2023"),

    # risk_choropleth — the plan's flagship: pre-1981 wood × flood depth.
    GallerySpec("koto", "risk_choropleth", "Kōtō — Risk Choropleth", "Pre-1981 wood × flood depth · PLATEAU 2023"),
    GallerySpec("edogawa", "risk_choropleth", "Edogawa — Risk Choropleth", "Pre-1981 wood × flood depth · PLATEAU 2023"),

    # wood_survivor — shitamachi wards have the densest 木造 / 準耐火造 grain.
    GallerySpec("shibuya", "wood_survivor", "Shibuya — Wood Survivor", "Wood / semi-fire-resistant · PLATEAU 2023"),
    GallerySpec("taito", "wood_survivor", "Taitō — Wood Survivor", "Wood / semi-fire-resistant · PLATEAU 2023"),
    GallerySpec("sumida", "wood_survivor", "Sumida — Wood Survivor", "Wood / semi-fire-resistant · PLATEAU 2023"),
    GallerySpec("kamakura", "wood_survivor", "Kamakura — Wood Survivor", "Structure-class detail · PLATEAU"),

    # age_rainbow — only cities with non-sentinel year_built coverage.
    GallerySpec("fukuoka", "age_rainbow", "Fukuoka — Building Age Rainbow", "Per-building year built · PLATEAU 2024", width=2000),
    GallerySpec("sapporo", "age_rainbow", "Sapporo — Building Age Rainbow", "Per-building year built · PLATEAU", width=1800),

    # Hazard confluence — wards with both flood and landslide coverage.
    GallerySpec("ota", "hazard_confluence", "Ōta — Hazard Confluence", "Overlap of PLATEAU hazard layers"),
    GallerySpec("setagaya", "hazard_confluence", "Setagaya — Hazard Confluence", "Overlap of PLATEAU hazard layers"),

    # Density hex — stations / commercial spines.
    GallerySpec("shinjuku", "density_hex", "Shinjuku — Density Hex", "Buildings per 250 m hex cell · PLATEAU"),
    GallerySpec("osaka", "density_hex", "Osaka — Density Hex", "Buildings per 250 m hex cell · PLATEAU 2024", width=1800),

    # Zoning mosaic — relies on plateau-bridge zoning_use column.
    GallerySpec("shibuya", "zoning_mosaic", "Shibuya — Zoning Mosaic", "用途地域 · PLATEAU 2023"),
    GallerySpec("chiyoda", "zoning_mosaic", "Chiyoda — Zoning Mosaic", "用途地域 · PLATEAU 2023"),

    # Mega-cities (700k+ buildings) — only cheap presets so the gallery
    # finishes in a reasonable wall-clock. density_hex aggregates centroids
    # in O(N) and is the cheapest preset on huge cities.
    GallerySpec("yokohama", "density_hex", "Yokohama — Density Hex", "Buildings per 250 m hex · PLATEAU", width=1600),
    GallerySpec("nagoya",   "density_hex", "Nagoya — Density Hex",   "Buildings per 250 m hex · PLATEAU", width=1600),
    GallerySpec("nagoya",   "height_topo", "Nagoya — Height Topo",   "Building height as topo · PLATEAU", width=1600),
)


REQUIRED_FIELD_BY_PRESET: dict[str, str] = {
    "use_mosaic": "usage",
    "height_topo": "height",
    "flood_depth": "usage",
    "risk_choropleth": "usage",
    "wood_survivor": "usage",
    "age_rainbow": "year_built",
    "hazard_confluence": "usage",
    "density_hex": "usage",
    "zoning_mosaic": "usage",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--out", default=Path("gallery"), type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    access = DataAccess(data_root=str(args.data_root))
    manifest_records: list[dict] = []
    t0 = time.perf_counter()

    for spec in MATRIX:
        # Pre-flight: skip if the required field has zero coverage in the manifest.
        try:
            dataset = access.load_city(spec.city, columns=["centroid_lon", "centroid_lat"])
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {spec.city}/{spec.preset}: cannot load — {exc}")
            continue
        field = REQUIRED_FIELD_BY_PRESET.get(spec.preset)
        if field and dataset.field_coverage.get(field, 0.0) == 0.0:
            print(f"[skip] {spec.city}/{spec.preset}: field_coverage[{field}]=0")
            continue

        out_path = args.out / f"{spec.city}_{spec.preset}.png"
        if args.dry_run:
            print(f"[dry] would render {out_path}")
            continue
        t1 = time.perf_counter()
        result = render(
            city=spec.city,
            preset=spec.preset,
            out=str(out_path),
            title=spec.title,
            subtitle=spec.subtitle,
            width=spec.width,
            theme=spec.theme,
            overwrite=True,
            data_root=str(args.data_root),
        )
        dt = time.perf_counter() - t1
        print(f"[ok ] {out_path}  ({result.width}×{result.height}, {dt:.1f}s)")
        for w in result.warnings:
            print(f"       warn: {w}")
        manifest_records.append(
            {
                **asdict(spec),
                "path": str(out_path),
                "width": result.width,
                "height": result.height,
                "attribution": result.attribution,
                "dataset_id": result.dataset_id,
                "elapsed_ms": result.elapsed_ms,
            }
        )

    (args.out / "gallery_manifest.json").write_text(
        json.dumps({"items": manifest_records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nDone in {time.perf_counter() - t0:.1f}s. {len(manifest_records)} renders.")


if __name__ == "__main__":
    main()

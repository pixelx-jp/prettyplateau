"""Render the same preset across many cities in one Python loop.

Demonstrates the structured `RenderRequest` API, parallel I/O safety, and
the warning shape returned by each render. The actual launch gallery uses
`scripts/build_gallery.py` (a richer matrix); this script is the
minimum-viable batch loop people can copy and modify.

  uv run examples/batch_cities.py
"""

from __future__ import annotations

from pathlib import Path

from prettyplateau import render
from prettyplateau.data.access import DataAccess


CITIES = ["shibuya", "shinjuku", "minato", "chiyoda"]
PRESET = "height_topo"


def main() -> None:
    out_dir = Path(__file__).parent / "out" / "batch"
    out_dir.mkdir(parents=True, exist_ok=True)
    access = DataAccess(data_root="../plateau-core")
    for city in CITIES:
        dataset = access.load_city(city, columns=["centroid_lon", "centroid_lat"])
        if dataset.field_coverage.get("height", 0.0) < 0.5:
            print(f"[skip] {city}: height coverage {dataset.field_coverage.get('height', 0):.0%}")
            continue
        out_path = out_dir / f"{city}_{PRESET}.png"
        result = render(
            city=city,
            preset=PRESET,
            out=str(out_path),
            title=f"{city.title()} — Height Topo",
            subtitle="Per-building height · PLATEAU",
            width=2400,
            overwrite=True,
            data_root="../plateau-core",
        )
        print(f"[ok ] {result.path}  warnings={result.warnings}")


if __name__ == "__main__":
    main()

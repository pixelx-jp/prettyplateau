"""Render a single 4K poster for printing.

The minimum-viable Python example. Useful as the "did install work?" smoke
test. Runs in ~20 seconds on a Tokyo ward.

  uv run examples/render_poster.py
"""

from __future__ import annotations

from pathlib import Path

from prettyplateau import render


def main() -> None:
    result = render(
        city="shibuya",
        preset="use_mosaic",
        out=str(Path(__file__).parent / "out" / "shibuya_use_mosaic.png"),
        title="Shibuya — Use Mosaic",
        subtitle="Per-building usage · PLATEAU 2023",
        width=3840,
        dpi=300,
        overwrite=True,
        data_root="../plateau-core",
    )
    print(f"wrote {result.path} ({result.width}×{result.height}, {result.elapsed_ms} ms)")
    print(result.attribution)


if __name__ == "__main__":
    main()

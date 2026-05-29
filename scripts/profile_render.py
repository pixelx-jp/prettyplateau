"""Profile a single render to identify the next perf bottleneck.

Run:
  python scripts/profile_render.py --city shibuya --preset use_mosaic
"""

from __future__ import annotations

import argparse
import cProfile
import pstats
from pathlib import Path

from prettyplateau.api.render import render


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="shibuya")
    ap.add_argument("--preset", default="use_mosaic")
    ap.add_argument("--data-root", default="../plateau-core")
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--out", default="/tmp/profile_out.png")
    args = ap.parse_args()

    pr = cProfile.Profile()
    pr.enable()
    render(
        city=args.city,
        preset=args.preset,
        out=args.out,
        width=args.width,
        data_root=args.data_root,
        overwrite=True,
    )
    pr.disable()

    stats = pstats.Stats(pr).sort_stats("cumulative")
    stats.print_stats(30)


if __name__ == "__main__":
    main()

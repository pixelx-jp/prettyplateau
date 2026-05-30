#!/usr/bin/env python3
"""Build the static gallery site from gallery/gallery_manifest.json.

Emits a self-contained `_site/` (index.html + copied image/video assets) ready
for GitHub Pages. Generated in CI so the page never drifts from the manifest.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GALLERY = ROOT / "gallery"
OUT = ROOT / "_site"

PRESET_TITLES = {
    "use_mosaic": "Use Mosaic",
    "height_topo": "Height Topo",
    "flood_depth": "Flood Depth",
    "risk_choropleth": "Risk Choropleth",
    "wood_survivor": "Wood Survivor",
    "age_rainbow": "Building Age Rainbow",
    "hazard_confluence": "Hazard Confluence",
    "density_hex": "Density Hex",
    "zoning_mosaic": "Zoning Mosaic",
    "survivor_timeline": "Survivor Timeline",
}


def title(s: str) -> str:
    return PRESET_TITLES.get(s, s.replace("_", " ").title())


def main() -> None:
    items = json.loads((GALLERY / "gallery_manifest.json").read_text(encoding="utf-8"))["items"]
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    cards = []
    for it in items:
        src = ROOT / it["path"]
        if not src.is_file():
            continue
        name = src.name
        shutil.copy2(src, OUT / name)
        city = html.escape(it.get("city", "").title())
        preset = html.escape(title(it.get("preset", "")))
        is_video = it.get("format") == "mp4" or name.endswith(".mp4")
        media = (
            f'<video src="{name}" controls preload="none" loop muted playsinline></video>'
            if is_video
            else f'<img src="{name}" alt="{city} — {preset}" loading="lazy" />'
        )
        cards.append(
            f'<figure><a href="{name}" target="_blank" rel="noopener">{media}</a>'
            f"<figcaption><strong>{city}</strong> · {preset}</figcaption></figure>"
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>prettyplateau — gallery</title>
<meta name="description" content="Print-quality city visualizations from Project PLATEAU (Japan's national 3D urban dataset), rendered with prettyplateau. CC BY 4.0." />
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.5; background: #fafafa; color: #1a1a1a; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #111; color: #eee; }} }}
  header {{ max-width: 1100px; margin: 0 auto; padding: 48px 20px 8px; }}
  h1 {{ margin: 0 0 4px; font-size: 2rem; }}
  .lede {{ font-size: 1.05rem; opacity: .8; margin: 0 0 8px; }}
  .links a {{ margin-right: 14px; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 16px 20px 64px;
    display: grid; gap: 22px; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }}
  figure {{ margin: 0; background: #fff; border-radius: 10px; overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,.12); }}
  @media (prefers-color-scheme: dark) {{ figure {{ background: #1c1c1c; }} }}
  figure img, figure video {{ width: 100%; height: auto; display: block; }}
  figcaption {{ padding: 10px 14px; font-size: .9rem; }}
  footer {{ max-width: 1100px; margin: 0 auto; padding: 0 20px 64px; font-size: .85rem; opacity: .75; }}
  a {{ color: #2563eb; }}
  @media (prefers-color-scheme: dark) {{ a {{ color: #7aa2ff; }} }}
</style>
</head>
<body>
<header>
  <h1>prettyplateau gallery</h1>
  <p class="lede">Print-quality city visualizations from
    <a href="https://www.mlit.go.jp/plateau/">Project PLATEAU</a>, rendered with
    the <code>prettyplateau</code> CLI.</p>
  <p class="links">
    <a href="https://pypi.org/project/prettyplateau/">PyPI</a>
    <a href="https://github.com/pixelx-jp/prettyplateau">GitHub</a>
  </p>
  <p class="lede"><code>pip install prettyplateau</code> · <code>prettyplateau fetch shibuya</code> · <code>prettyplateau render --city shibuya --preset use_mosaic --out shibuya.png</code></p>
</header>
<main>
{chr(10).join(cards)}
</main>
<footer>
  All images © Project PLATEAU / 国土交通省 (MLIT), CC BY 4.0. prettyplateau code is MIT.
  Built by <a href="https://yodolabs.jp">Yodo Labs</a>.
</footer>
</body>
</html>
"""
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {OUT/'index.html'} with {len(cards)} cards")


if __name__ == "__main__":
    main()

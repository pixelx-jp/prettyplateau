# Changelog

All notable changes to `prettyplateau` will be documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] — 2026-05-31

### Performance
- `load_buildings` now decodes the WKB geometry column with the vectorized
  `shapely.from_wkb` (GEOS reader in C) instead of a per-row `wkb.loads` map —
  ~10× faster geometry decode at 300k+ buildings. Mirrored in the
  plateau-bridge adapter.
- The render path projects the parquet to only the columns the preset declares
  it uses (required + optional), intersected with the file schema — skipping
  the heavy 3D geometry / unused attribute columns on every load.
- `load_palette` is cached so bundled palette JSON is parsed once per process,
  and the ~10 MB bundled admin GeoJSON is parsed once and reused across cities.
- `survivor_timeline` builds each animation frame's fills with vectorized numpy
  selection instead of a per-building Python loop over `palette.color_for`
  (dropped ~50M dict lookups on a 180-frame × 300k-building render). Output is
  unchanged.

## [0.1.3] — 2026-05-31

### Performance
- Polygon layers now draw through a single `PathCollection` over raw matplotlib
  `Path`s instead of wrapping every ring in a `PathPatch` for a
  `PatchCollection`. Coordinates are pulled from shapely in bulk via
  `get_coordinates`. ~2–2.5× faster rendering on dense cities (e.g. Shinjuku
  ~57k buildings), pixel-identical output (verified by the visual baselines).

## [0.1.1] — 2026-05-29

### Fixed
- README image URLs use absolute GitHub raw paths so they render on the
  PyPI project page (relative paths only work on github.com).
- CI: ruff lint clean across the suite; mp4-card test threshold loosened
  for synthetic-fixture H.264 noise levels across macOS / Linux ffmpeg
  builds.

## [0.1.0] — 2026-05-29 (yanked — README images didn't render on PyPI)

### Plan-alignment refactor (self-review pass against `plan-prettyplateau.md`)
- **`risk_choropleth` renamed** to match plan vocabulary — it is now the
  compound wood × pre-1981 × flood-depth preset (plan's "flagship
  intersection of era × structure × hazard"). The previous simple
  flood-depth preset moved to `flood_depth`.
- **Survivor Timeline** defaults now match the plan: 60-second mp4 (180
  frames at 3 fps); event-year markers include 1990 alongside
  1923/1945/1964/1981/2011.
- **`render(return_scene=True)`** and **`out=None` → Figure** code paths
  implemented and tested.
- **Theme transforms wired** — `line_width_scale`, `contrast`, and
  `paper_texture` now actually affect the rendered canvas; reserved
  palette keys (`unknown`, `no_data`, hazard ordering) cannot be remapped
  by any theme.
- **`FontManager.resolve_text_font(text)`** picks Noto Sans CJK JP for any
  CJK-containing text and Inter for Latin-only text; Inter Regular +
  SemiBold bundled.
- **CLI `--attribution-corner`** allows position (but not deletion) per
  plan's "CLI flag 可调位置不可关闭".
- **PresetMetadata.supports_variants** added; `required_hazards` aliased
  to plan-named `hazard_requirements`.
- **Themes loadable from `assets/themes/*.json`** with a `register_theme`
  hook for future entry-point-driven community themes.
- **Plan-shaped module surfaces** added: `core/registry.py`,
  `core/context.py`, `renderers/base.py` (Renderer Protocol),
  `style/seasonal.py`, `style/legends.py`, `style/typography.py`,
  `compose/layout.py`, `compose/annotations.py`, `compose/watermark.py`,
  `animation/timeline.py`, `animation/keyframes.py`,
  `animation/captions.py`, `export/glb_metadata.py`,
  `presets/variants.py`, `data/attribution.py`, `_core_lite/filters.py`,
  `_core_lite/attribution.py`, `testing/baselines.py`.
- **`tests/integration/`** + **`tests/cli/`** subtrees added per plan
  layout.
- **Semantic regression assertions** added per preset (plan's "视觉回归
  细节" list): `age_rainbow` unknown-count, `risk_choropleth` +
  `flood_depth` no-data legend, `survivor_timeline` monotonically
  non-decreasing building count, etc.
- **Wood Survivor** now carries an air-raid-context annotation per plan's
  "红色高亮 + 空袭范围参考".
- **Composer auto-shrinks** title/subtitle fonts and adapts legend
  layout for small canvases (< 1500px width).

### Added (prior milestones)
- **Admin-boundary layer** — every built-in preset now draws the city silhouette under the buildings layer when plateau-bridge ships a matching geojson for that JIS city_code.
- **Four new v2 presets**:
  - `compound_risk` — pre-1981 wood × river-flood depth intersection (plan's flagship).
  - `hazard_confluence` — per-building tally of overlapping PLATEAU hazards.
  - `density_hex` — building-count aggregation onto a hex lattice.
  - `zoning_mosaic` — per-building 用途地域 (MLIT 13-class scheme).
- **Bundled Noto Sans CJK JP** — Japanese glyphs in titles, legends, and notes resolve out of the box.
- **Multi-format export** — `prettyplateau render --out 'shibuya.{png,svg,pdf}'` writes all three formats from one data load and one rendered figure.
- **Sidecar metadata** — `--sidecar` writes a `{out}.json` next to each artifact with full request + scene + attribution metadata.
- **Survivor timeline event-year visual** — bottom strip annotates 1923 / 1945 / 1964 / 1981 / 2011 with a current-year accent callout.
- **3 runnable `examples/` scripts** — `render_poster.py`, `batch_cities.py`, `custom_preset.py`.
- **`gallery/README.md`** — city-by-city index with embedded thumbnails for the 30-image launch matrix.
- `prettyplateau create-preset <id>` — scaffolds a runnable third-party preset package (preset module + palette JSON + smoke test + pyproject with entry-point registration).
- `MatplotlibRenderer.render_persistent` / `update_layer_fills` — patch-collection reuse for animations. Cuts 12-frame Fukuoka mp4 from 287s to 54s (5.3×).
- `tests/visual/baselines/` — committed dHash + PNG baselines for the 5 static presets. Three-tier compare: dHash (≤4 bit drift), RMS (<0.10), palette presence. Refresh via `pytest --update-baselines`.

### Fixed
- mp4 export now crops odd-pixel canvas dimensions to even, so libx264 + yuv420p don't reject the stream with `height must be even`.
- Survivor timeline year-range now ignores the plateau-bridge `year_built = 1` sentinel — early frames no longer waste 70% of the timeline on pre-Meiji buildings that don't actually exist in the data.
- `lookup_admin_boundary` gracefully recovers from shapely topology exceptions (some PLATEAU admin polygons have unenclosed holes — e.g. Edogawa).

## [0.1.0] — 2026-05-29

First public release.

### Added
- Public `prettyplateau.render()` and `list_presets()` API; CLI entry point.
- Six built-in presets:
  - `age_rainbow` (static) — per-building year_built rainbow with `unknown` grey.
  - `wood_survivor` (static) — wood + era highlight with `fire_resistance` fallback.
  - `use_mosaic` (static) — per-building usage palette.
  - `risk_choropleth` (static) — river-flood depth with mandatory no-data legend.
  - `height_topo` (static) — building height topographic ramp.
  - `survivor_timeline` (animation) — mp4 timeline with `demolished structures absent` caption.
- Six themes: `default`, `print`, `sakura`, `summer_matsuri`, `snow`, `neon_night`.
- Non-bypassable CC BY 4.0 attribution injection:
  - PNG via tEXt/iTXt metadata + visible corner text.
  - SVG via RDF/Dublin Core `<metadata>` + visible `<text>`.
  - PDF via document info dict + visible text.
  - mp4 via container metadata + 2-second end card.
- `plateau_bridge` adapter (`data.core_adapter`) with `_core_lite` offline fallback.
- Animation pipeline via `imageio-ffmpeg` (optional `prettyplateau[animation]` extra).
- Synthetic-fixture-based visual smoke tests covering all 5 static presets.

### Known limits
- Animation render time scales O(frames × buildings). Use `-O max_buildings=N` to subsample for mega-cities.
- Wood detection relies on `structure="wood"` plus a `fire_resistance` fallback because some plateau-bridge cities collapse wood into the `other` structure bucket.
- `year_built = 1` is treated as unknown (sentinel value emitted by some plateau-bridge upstreams).

[Unreleased]: https://github.com/pixelx-jp/prettyplateau/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/pixelx-jp/prettyplateau/releases/tag/v0.1.0

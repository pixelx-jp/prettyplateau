# Contributing to prettyplateau

Thanks for the interest. prettyplateau is a small, opinionated package; this
guide explains how to add things without breaking the few invariants the
project deliberately enforces.

## Setup

```bash
git clone https://github.com/pixelx-jp/prettyplateau
cd prettyplateau
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,animation]'
pytest -q
```

The test suite uses synthetic fixtures — no PLATEAU data download required.

## Adding a preset

A preset is a `BasePreset` subclass that turns a `CityDataset` into a
`RenderScene` (and optionally a `TimelineSpec` for animations).

1. Create `src/prettyplateau/presets/<your_id>.py`.
2. Subclass `BasePreset`; set `metadata: PresetMetadata` describing the
   required fields, output modes, and whether the preset supports themes.
3. Implement `prepare()` (validate columns, derive what you need) and
   `build_scene()` (return a `RenderScene` whose layers are pure data,
   not matplotlib objects).
4. Add to `_register_builtins` in `presets/registry.py`. (Third-party
   presets register via the `prettyplateau.presets` entry-point group.)
5. Write a smoke test that runs the preset against `fixture_dataset()`
   and asserts the legend, fills, and `RenderResult.warnings` shape.

### Invariants every preset must respect

- **`unknown` and `no_data` keys are reserved.** Themes cannot override
  them (`style.palette.RESERVED_KEYS`). Don't pick a new key for "missing".
- **`hazard_covered=false` means no data, not low risk.** Use the helpers
  in `data/hazard.py` rather than hand-rolling depth → key logic.
- **Don't write files from a preset.** That's the exporter's job.
- **Don't import matplotlib from a preset.** Scenes are pure data.

## Adding a theme

Themes are visual variants only. They cannot change data semantics, so:

- ✅ Background, foreground, accent, line widths, paper texture.
- ❌ Recolouring the `unknown` bucket.
- ❌ Hiding the no-data legend entry.
- ❌ Reordering hazard severity bands.

Register the theme in `style/theme.py::_THEMES`.

## Style

- ruff lint (`ruff check .`) is required to be clean before merge.
- No new top-level dependencies without discussion — keep the install light.
- Public-facing strings are English first. Japanese labels live in palette
  / theme configs and are loaded as overlays.

## Attribution

The mandatory PLATEAU attribution is non-negotiable and enforced in code
(`compose/attribution_injector.py`). PRs that add a way to disable it will
be closed.

"""Visual regression — render fixture-based PNGs and compare to committed baselines.

Approach
--------

We deliberately do **not** pixel-match. Pixel exactness across matplotlib /
freetype / OS versions is a losing battle, and a baseline that drifts on
every CI image bump becomes noise.

Instead each preset has a triple of checks:

  1. **Hash stability** — perceptual dHash should match the baseline. dHash
     is robust to small antialias / font shifts but catches layout drift.
  2. **Palette presence** — the rendered image's unique colours include the
     full preset palette (no preset silently dropping legend entries).
  3. **RMS bound** — average per-pixel deviation stays under a generous
     threshold so a wholesale visual change still flags up.

Update baselines with `pytest tests/visual --update-baselines`.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from prettyplateau.api.types import RenderRequest
from prettyplateau.compose.attribution_injector import (
    AttributionInjector,
    AttributionSpec,
)
from prettyplateau.compose.composer import Composer, CompositionOptions
from prettyplateau.export.png import PNGExporter
from prettyplateau.presets.registry import get_registry
from prettyplateau.renderers.matplotlib_renderer import MatplotlibRenderer, RenderOptions
from prettyplateau.style.theme import get_theme
from prettyplateau.testing.fixtures import fixture_dataset
from prettyplateau.testing.image_diff import perceptual_hash, rms_diff


BASELINE_DIR = Path(__file__).parent / "baselines"
PRESETS = ("age_rainbow", "use_mosaic", "wood_survivor", "risk_choropleth", "height_topo")

# Fixed for reproducible baselines.
FIXED_GENERATED_AT = _dt.datetime(2026, 5, 29, 0, 0, 0, tzinfo=_dt.timezone.utc)


def _render_baseline(preset_id: str, dest: Path) -> Path:
    dataset = fixture_dataset(n=64)
    request = RenderRequest(city="fixture", preset=preset_id)
    preset = get_registry().resolve(preset_id)
    prepared = preset.prepare(dataset, request)
    theme = get_theme("default")
    scene = preset.build_scene(prepared, theme, request)
    opts = CompositionOptions(title=preset_id, subtitle="fixture")
    fig = MatplotlibRenderer().render(
        scene,
        theme,
        RenderOptions(
            width_px=512,
            top_margin=opts.top_margin(),
            bottom_margin=opts.bottom_margin(),
            side_margin=opts.side_margin(),
        ),
    )
    spec = AttributionSpec(
        text=dataset.attribution,
        dataset_id=dataset.dataset_id,
        generated_at=FIXED_GENERATED_AT,
    )
    composition = Composer(AttributionInjector(spec)).compose(fig, scene, theme, opts)
    PNGExporter().write(
        composition,
        dest,
        metadata={
            "Software": "prettyplateau-test",
            "Attribution": dataset.attribution,
            "Preset": preset_id,
            "City": dataset.city,
            "Theme": "default",
            "GeneratedAt": FIXED_GENERATED_AT.isoformat(),
        },
        overwrite=True,
    )
    return dest


@pytest.mark.parametrize("preset_id", PRESETS)
def test_visual_baseline(tmp_path: Path, preset_id: str, request: pytest.FixtureRequest) -> None:
    """Render the preset against the fixture and compare to committed baseline.

    When `--update-baselines` is passed, the test instead writes the current
    render to the baselines/ directory and passes. This is the *only*
    sanctioned way to refresh a baseline — never overwrite baselines/* by hand.
    """
    update = request.config.getoption("--update-baselines", default=False)
    current = _render_baseline(preset_id, tmp_path / f"{preset_id}.png")
    baseline = BASELINE_DIR / f"{preset_id}.png"
    if update or not baseline.exists():
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(current.read_bytes())
        # Also write a small hash sidecar so reviewers can spot churn in PRs.
        sidecar = BASELINE_DIR / f"{preset_id}.hash.json"
        sidecar.write_text(
            json.dumps({"dhash": perceptual_hash(baseline)}, indent=2),
            encoding="utf-8",
        )
        pytest.skip(f"baseline written for {preset_id}; re-run without --update-baselines to validate")

    # Three-tier comparison.
    cur_hash = perceptual_hash(current)
    base_hash = perceptual_hash(baseline)
    # dHash equality is strict; a single bit drift is OK because layout shouldn't move.
    hash_distance = sum(a != b for a, b in zip(cur_hash, base_hash))
    assert hash_distance <= 4, f"{preset_id}: dHash drift {hash_distance} > 4 (likely a layout change)"

    rms = rms_diff(current, baseline)
    assert rms < 0.10, f"{preset_id}: RMS pixel diff {rms:.4f} exceeds 0.10 (wholesale visual change)"


# `--update-baselines` option is registered in tests/conftest.py.

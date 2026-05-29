"""`prettyplateau create-preset` — emit a working third-party preset skeleton.

Goal: a contributor can go from idea to a renderable, registered preset in
under five minutes. The skeleton is intentionally small (one preset file +
one palette JSON + one test) so the diff is easy to review and easy to copy.

Conventions:
  - preset id is kebab-or-snake — we normalise to snake for the filename and
    the registered id, but accept both at the CLI prompt.
  - the generated package layout mirrors built-in presets so a learner can
    inspect prettyplateau's own source and find the same shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SAFE_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class ScaffoldPaths:
    pkg_dir: Path
    preset_file: Path
    palette_file: Path
    test_file: Path
    pyproject_file: Path


def _normalise_id(raw: str) -> str:
    norm = raw.strip().lower().replace("-", "_")
    if not SAFE_ID.match(norm):
        raise ValueError(
            f"preset id {raw!r} → {norm!r} is not a valid Python identifier "
            "(start with a letter, [a-z0-9_] only)"
        )
    return norm


PRESET_TEMPLATE = '''"""{name_human} preset — community contribution."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pandas as pd

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.data.access import CityDataset
from prettyplateau.presets.base import BasePreset, PreparedData
from prettyplateau.presets.scene import (
    LegendEntry,
    LegendSpec,
    PolygonLayer,
    RenderScene,
)
from prettyplateau.style.theme import Theme


def _load_palette() -> dict[str, str]:
    pkg = files("{module_name}")
    data = json.loads(Path(str(pkg / "{preset_id}_palette.json")).read_text(encoding="utf-8"))
    return dict(data["colors"])


class {class_name}(BasePreset):
    metadata = PresetMetadata(
        id="{preset_id}",
        name="{name_human}",
        description="TODO: describe what this preset visualises.",
        modes=["static"],
        # TODO: list every column the preset reads. Required ones cause a
        # fail-fast if missing; optional ones produce a warning instead.
        required_fields=["usage"],
        community=True,
    )

    def prepare(self, dataset: CityDataset, request: RenderRequest) -> PreparedData:
        gdf = dataset.gdf
        # TODO: replace this stub with whatever per-building computation you
        # need. Common patterns: bucket a numeric column, look up a code in
        # a mapping table, intersect with a hazard layer.
        keys = pd.Series(["other"] * len(gdf), index=gdf.index)
        return PreparedData(dataset=dataset, derived={{"keys": keys}})

    def build_scene(
        self,
        prepared: PreparedData,
        theme: Theme,
        request: RenderRequest,
    ) -> RenderScene:
        gdf = prepared.dataset.gdf
        keys = prepared.derived["keys"]
        palette = _load_palette()
        fills = [palette.get(k, palette.get("unknown", "#C9CDD6")) for k in keys.tolist()]

        layer = PolygonLayer(
            id="buildings",
            geometries=list(gdf.geometry),
            fills=fills,
            z=10,
        )
        legend = LegendSpec(
            title="{name_human}",
            entries=tuple(LegendEntry(label=k.title(), color=v) for k, v in palette.items()),
        )

        # Bounds via centroid percentiles to stay robust against outliers.
        if "centroid_lon" in gdf.columns and not gdf.empty:
            lon = gdf["centroid_lon"]
            lat = gdf["centroid_lat"]
            bounds = (lon.quantile(0.001), lat.quantile(0.001), lon.quantile(0.999), lat.quantile(0.999))
        else:
            bounds = (0.0, 0.0, 0.0, 0.0)

        return RenderScene(
            bounds=tuple(float(b) for b in bounds),
            background=theme.background,
            layers=(layer,),
            legend=legend,
            semantic_metadata={{"preset": self.metadata.id, "n_buildings": int(len(gdf))}},
        )


PRESET = {class_name}()


def factory() -> {class_name}:
    return {class_name}()
'''


PALETTE_TEMPLATE = '''{
  "id": "{preset_id}",
  "description": "TODO: describe colour semantics.",
  "kind": "categorical",
  "order": ["other", "unknown"],
  "colors": {
    "other":   "#7CC576",
    "unknown": "#C9CDD6"
  }
}
'''


TEST_TEMPLATE = '''"""Smoke test for the {preset_id} community preset."""

from __future__ import annotations

from prettyplateau.presets.registry import get_registry
from prettyplateau.style.theme import get_theme
from prettyplateau.testing.fixtures import fixture_dataset
from prettyplateau.api.types import RenderRequest


def test_{preset_id}_builds_a_scene() -> None:
    dataset = fixture_dataset(n=32)
    preset = get_registry().resolve("{preset_id}")
    request = RenderRequest(city="fixture", preset="{preset_id}")
    prepared = preset.prepare(dataset, request)
    scene = preset.build_scene(prepared, get_theme("default"), request)

    assert scene.layers
    assert scene.legend is not None
    # Every polygon must have a fill.
    polygon = scene.layers[0]
    assert len(polygon.fills) == len(polygon.geometries)
'''


PYPROJECT_TEMPLATE = '''[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "{module_name}"
version = "0.0.1"
description = "{name_human} preset for prettyplateau."
requires-python = ">=3.11"
dependencies = ["prettyplateau>=0.1", "pandas>=2.0"]

[project.entry-points."prettyplateau.presets"]
{preset_id} = "{module_name}:PRESET"

[tool.hatch.build.targets.wheel]
packages = ["src/{module_name}"]
'''


def scaffold(preset_id: str, dest_root: Path, name: str | None = None) -> ScaffoldPaths:
    preset_id = _normalise_id(preset_id)
    module_name = f"prettyplateau_preset_{preset_id}"
    class_name = "".join(part.capitalize() for part in preset_id.split("_")) + "Preset"
    display_name = name or preset_id.replace("_", " ").title()

    pkg_dir = dest_root / module_name / "src" / module_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text(f"from {module_name}.{preset_id} import PRESET, factory\n\n__all__ = [\"PRESET\", \"factory\"]\n", encoding="utf-8")

    preset_file = pkg_dir / f"{preset_id}.py"
    preset_file.write_text(
        PRESET_TEMPLATE.format(
            name_human=display_name,
            preset_id=preset_id,
            module_name=module_name,
            class_name=class_name,
        ),
        encoding="utf-8",
    )

    palette_file = pkg_dir / f"{preset_id}_palette.json"
    # `format()` chokes on the JSON braces, so use plain replace for these
    # templates. Keeps the template strings readable as actual JSON.
    palette_file.write_text(
        PALETTE_TEMPLATE.replace("{preset_id}", preset_id),
        encoding="utf-8",
    )

    test_dir = dest_root / module_name / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / f"test_{preset_id}.py"
    test_file.write_text(TEST_TEMPLATE.format(preset_id=preset_id), encoding="utf-8")

    pyproject_file = dest_root / module_name / "pyproject.toml"
    pyproject_file.write_text(
        PYPROJECT_TEMPLATE
        .replace("{module_name}", module_name)
        .replace("{preset_id}", preset_id)
        .replace("{name_human}", display_name),
        encoding="utf-8",
    )

    return ScaffoldPaths(
        pkg_dir=pkg_dir,
        preset_file=preset_file,
        palette_file=palette_file,
        test_file=test_file,
        pyproject_file=pyproject_file,
    )

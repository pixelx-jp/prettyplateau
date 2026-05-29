"""RenderContext — the per-call value object shared across pipeline stages.

The render pipeline (`api/render.py`) historically passed disparate
arguments to each stage (`renderer`, `composer`, `exporter`, `animator`)
which made the call site fragile. `RenderContext` collects those values
into one immutable container so any future refactor (e.g. swapping in a
Cairo renderer) only needs to receive the context and the stage-specific
options.

Today the pipeline still passes individual args — `RenderContext` is
exposed so third-party orchestrators (CI scripts, Jupyter wrappers) can
construct one directly without re-deriving everything from a `RenderRequest`.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from prettyplateau.api.types import RenderRequest
from prettyplateau.data.access import CityDataset


@dataclass(frozen=True)
class RenderContext:
    """Snapshot of inputs and derived state for one render call.

    Stage code (Preset, Renderer, Composer, Exporter) reads this; nothing
    writes back. Mutating in-flight state belongs in the stage's own
    return type (e.g. `ComposedArtifact`), not here.
    """

    request: RenderRequest
    dataset: CityDataset
    generated_at: _dt.datetime
    backend: str  # "plateau_bridge" | "core_lite"
    data_root: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def attribution_text(self) -> str:
        return self.dataset.attribution

    @property
    def dataset_id(self) -> str | None:
        return self.dataset.dataset_id

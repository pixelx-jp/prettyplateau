"""Preset base class and supporting types.

A preset is a pure-ish object: declare metadata, declare data requirements,
prepare derived columns, build a scene (and optionally a timeline). Presets
must not perform IO, must not write files, must not import matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from prettyplateau.api.types import PresetMetadata, RenderRequest
from prettyplateau.presets.scene import RenderScene

if TYPE_CHECKING:
    from prettyplateau.data.access import CityDataset
    from prettyplateau.style.theme import Theme


@dataclass(frozen=True)
class DataRequirement:
    """What a preset needs from `DataAccess`."""

    city: str
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()
    required_hazards: tuple[str, ...] = ()
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class PreparedData:
    """Output of `Preset.prepare`: a city dataset plus derived columns and notes."""

    dataset: "CityDataset"
    derived: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimelineFrame:
    """A single keyframe in an animation timeline."""

    t: float  # 0..1
    label: str
    scene: RenderScene


@dataclass(frozen=True)
class TimelineSpec:
    duration_seconds: float
    fps: int
    frames: tuple[TimelineFrame, ...]
    caption: str | None = None


class BasePreset:
    """Concrete presets subclass this. Static presets implement build_scene;
    animation presets override build_timeline and set `metadata.modes`."""

    metadata: PresetMetadata

    def required_data(self, request: RenderRequest) -> DataRequirement:
        return DataRequirement(
            city=request.city,
            required_fields=tuple(self.metadata.required_fields),
            optional_fields=tuple(self.metadata.optional_fields),
            required_hazards=tuple(self.metadata.required_hazards),
            bbox=request.bbox,
        )

    def prepare(self, dataset: "CityDataset", request: RenderRequest) -> PreparedData:
        return PreparedData(dataset=dataset)

    def build_scene(self, prepared: PreparedData, theme: "Theme", request: RenderRequest) -> RenderScene:
        raise NotImplementedError

    def build_timeline(
        self, prepared: PreparedData, theme: "Theme", request: RenderRequest
    ) -> TimelineSpec | None:
        return None

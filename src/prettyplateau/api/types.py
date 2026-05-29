"""Public, stable types for the prettyplateau API.

These cross the package boundary; any structural change needs a version bump.
Internal types live in `prettyplateau.core` or alongside their consumers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OutputFormat = Literal["png", "svg", "pdf", "mp4"]
RenderMode = Literal["static", "animation"]


class RenderRequest(BaseModel):
    """User-facing render request, used by both CLI and Python API."""

    model_config = ConfigDict(extra="forbid")

    city: str
    preset: str
    out: str | None = None
    format: OutputFormat | None = None
    theme: str = "default"
    bbox: tuple[float, float, float, float] | None = None
    width: int | None = None
    height: int | None = None
    dpi: int = 300
    title: str | None = None
    subtitle: str | None = None
    overwrite: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class RenderResult(BaseModel):
    """Result of a render call.

    When the caller passed `out=None`, `path` is `None` and either `figure`
    (a matplotlib `Figure`) or `scene` (a `RenderScene`) carry the
    in-memory artifact, depending on `return_scene`. Attribution is *still*
    included on the in-memory figure — only the exporter step is skipped.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    path: str | None
    format: OutputFormat
    preset: str
    city: str
    dataset_id: str | None
    attribution: str
    width: int
    height: int
    elapsed_ms: int
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # In-memory returns when `out` is None. Both are excluded from the
    # pydantic schema for serialisation but accessible on the instance.
    figure: Any = Field(default=None, exclude=True)
    scene: Any = Field(default=None, exclude=True)


class PresetMetadata(BaseModel):
    """Self-describing metadata for one preset.

    Field names follow the plan vocabulary where it exists; otherwise we
    pick clearer Python conventions.

      - `modes`              — what render modes this preset supports.
                               Plan calls this `output_modes`/`supports_animation`;
                               a single list expresses both without ambiguity.
      - `required_fields`    — columns that MUST exist or render fails fast.
      - `optional_fields`    — columns the preset uses if present; warns otherwise.
      - `hazard_requirements`/ `required_hazards` — alias pair. Plan calls the
                               field `hazard_requirements`; the original code
                               used `required_hazards`. Both names point at the
                               same list so old call sites keep working.
      - `supports_themes`    — false ⇒ all theme overrides ignored at compose.
      - `supports_variants`  — true ⇒ preset can be re-skinned by community
                               ThemeTransform packages; false ⇒ visual semantics
                               are too tight to permit overlays (e.g. for
                               hazard severity bands).
      - `community`          — registered through entry-points, not built-in.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    name: str
    description: str
    modes: list[RenderMode]
    required_fields: list[str]
    optional_fields: list[str] = Field(default_factory=list)
    hazard_requirements: list[str] = Field(default_factory=list, alias="required_hazards")
    default_format: OutputFormat = "png"
    supports_themes: bool = True
    supports_variants: bool = True
    community: bool = False

    @property
    def required_hazards(self) -> list[str]:
        """Back-compat alias for the plan-vocabulary `hazard_requirements`."""
        return self.hazard_requirements

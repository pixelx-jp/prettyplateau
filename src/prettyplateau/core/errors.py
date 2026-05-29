"""Typed errors for prettyplateau.

The hierarchy lets the CLI surface user-friendly messages while preserving
debug information; tests can assert specific subclasses without string matching.
"""

from __future__ import annotations


class PrettyPlateauError(Exception):
    """Base class for all prettyplateau-raised errors."""


class PresetNotFoundError(PrettyPlateauError):
    """The requested preset id is not registered."""


class PresetExecutionError(PrettyPlateauError):
    """A preset raised an exception during prepare/build_scene."""

    def __init__(self, preset_id: str, cause: BaseException) -> None:
        super().__init__(f"preset {preset_id!r} failed: {cause}")
        self.preset_id = preset_id
        self.cause = cause


class DataNotFoundError(PrettyPlateauError):
    """No PLATEAU dataset directory was found for the requested city."""


class DataFieldMissingError(PrettyPlateauError):
    """A field required by the preset is completely missing from the dataset."""

    def __init__(self, field: str, city: str) -> None:
        super().__init__(
            f"required field {field!r} is missing for city {city!r}; "
            f"this preset cannot run on this dataset"
        )
        self.field = field
        self.city = city


class AttributionError(PrettyPlateauError):
    """Attribution injection failed; output must be rejected."""


class RenderBackendError(PrettyPlateauError):
    """The chosen render backend could not be initialized."""


class ExportError(PrettyPlateauError):
    """An exporter failed to write the artifact."""


class BBoxEmptyError(PrettyPlateauError):
    """The requested bounding box contains no buildings."""

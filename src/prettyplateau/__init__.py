"""prettyplateau — print-quality city visualizations from Project PLATEAU data."""

from prettyplateau._version import __version__
from prettyplateau.api.render import list_presets, render
from prettyplateau.api.types import (
    OutputFormat,
    PresetMetadata,
    RenderRequest,
    RenderResult,
)
from prettyplateau.fonts import register_bundled_fonts
from prettyplateau.style.theme import Theme, get_theme

# Register bundled Noto Sans JP at import time so renders include Japanese
# glyphs out of the box regardless of host font configuration.
register_bundled_fonts()

__all__ = [
    "render",
    "list_presets",
    "RenderRequest",
    "RenderResult",
    "PresetMetadata",
    "OutputFormat",
    "Theme",
    "get_theme",
    "__version__",
]

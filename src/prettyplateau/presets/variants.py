"""Preset × theme variant compatibility checks.

Plan: "每个 preset 可声明 theme compatibility. 不兼容时给出 warning，
并回退到 default."

The `PresetMetadata.supports_variants` flag is the gross switch (preset
opts in to being themed at all). This module hosts the *fine-grained*
checks: e.g. risk_choropleth could declare it's not compatible with
saturated themes that would muddy the severity ordering. Today the
compatibility surface is conservative (always-compatible) so nothing
silently warns; future preset authors can extend this without touching
preset code.
"""

from __future__ import annotations

from prettyplateau.api.types import PresetMetadata


KNOWN_THEMES: frozenset[str] = frozenset(
    {"default", "print", "sakura", "summer_matsuri", "snow", "neon_night"}
)


def is_compatible(preset: PresetMetadata, theme_id: str) -> bool:
    """Return whether the preset accepts the given theme.

    A preset declines all themes when `supports_themes=False`. It declines
    community / unknown themes when `supports_variants=False`. Otherwise we
    accept — the renderer's reserved-key protection keeps semantic data
    safe.
    """
    if not preset.supports_themes and theme_id != "default":
        return False
    if not preset.supports_variants and theme_id not in KNOWN_THEMES:
        return False
    return True

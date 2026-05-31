"""Palette = preset-defined colour mapping for categorical or ordinal data.

Palettes are immutable; themes can supply overrides via `apply_theme_overrides`
but cannot remap semantic keys (unknown stays unknown, no-data stays no-data).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from pathlib import Path

from prettyplateau.style.theme import Theme

# Semantic keys that no theme can override. The plan calls these out
# explicitly: themes cannot recolour the unknown bucket, hide the no-data
# legend, or reorder hazard severity bands. The hazard ordering keys are
# included so a theme can tint them within reason but not swap red↔green.
RESERVED_KEYS: frozenset[str] = frozenset({
    "unknown",
    "no_data",
    # Survivor presets — `wood_year_unknown` is a partial-data sibling of
    # `unknown` and must stay distinguishable; the survivor narrative depends
    # on not silently bucketing unknown-year wood as either pre-1945 or
    # post-1980.
    "wood_year_unknown",
    # River-flood depth severity ordering (lower index = lower risk).
    "lt_05", "05_1", "1_3", "3_5", "5_10", "ge_10",
    # Hazard confluence ordering.
    "zero", "one", "two", "three_plus",
    # Compound risk severity ordering (headline = most severe).
    "pre81_wood_flood_high", "pre81_wood_flood_low", "pre81_wood_dry",
    "other_in_flood", "other_dry",
})


@dataclass(frozen=True)
class Palette:
    id: str
    description: str
    kind: str  # "categorical" | "ordinal" | "continuous"
    colors: dict[str, str] = field(default_factory=dict)
    order: tuple[str, ...] = ()

    def color_for(self, key: str | None) -> str:
        if key is None:
            return self.colors.get("unknown", "#9CA3AF")
        return self.colors.get(key, self.colors.get("unknown", "#9CA3AF"))

    def keys_in_order(self) -> Iterable[str]:
        if self.order:
            yield from self.order
        else:
            yield from self.colors.keys()


@cache
def load_palette(palette_id: str) -> Palette:
    # Bundled palette JSONs are read-only and small in number; parse each file
    # at most once per process. Palette is frozen so the cached value is safe to
    # share across every render/frame (presets call this on every build_scene).
    pkg = files("prettyplateau.assets.palettes")
    target = pkg / f"{palette_id}.json"
    data = json.loads(Path(str(target)).read_text(encoding="utf-8"))
    return Palette(
        id=data["id"],
        description=data.get("description", ""),
        kind=data.get("kind", "categorical"),
        colors=dict(data["colors"]),
        order=tuple(data.get("order", [])),
    )


def apply_theme_overrides(palette: Palette, theme: Theme) -> Palette:
    """Return a new palette with theme.palette merged in, ignoring reserved keys."""
    if not theme.palette:
        return palette
    new_colors = dict(palette.colors)
    for k, v in theme.palette.items():
        if k in RESERVED_KEYS:
            continue
        if k in new_colors:
            new_colors[k] = v
    return Palette(
        id=palette.id,
        description=palette.description,
        kind=palette.kind,
        colors=new_colors,
        order=palette.order,
    )

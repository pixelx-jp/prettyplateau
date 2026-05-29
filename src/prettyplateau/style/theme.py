"""Theme = visual variant. Themes never change data semantics.

`unknown` gray, `no-data` hashing, and hazard ordering are preset-owned and
cannot be overridden by a theme.

Themes load from JSON under `prettyplateau/assets/themes/*.json` so future
community themes can register via entry points without editing source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from importlib.resources import files
from pathlib import Path

_NOTO_JP = "Noto Sans JP"
_INTER = "Inter"


@dataclass(frozen=True)
class Theme:
    id: str
    name: str
    background: str
    foreground: str
    muted: str
    accent: str
    grid: str
    palette: dict[str, str] = field(default_factory=dict)
    font_primary: str = _NOTO_JP
    font_secondary: str = _INTER
    line_width_scale: float = 1.0
    contrast: float = 1.0
    paper_texture: bool = False


def _load_theme_file(path: Path) -> Theme:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Theme(
        id=data["id"],
        name=data["name"],
        background=data["background"],
        foreground=data["foreground"],
        muted=data["muted"],
        accent=data["accent"],
        grid=data["grid"],
        palette=dict(data.get("palette", {})),
        font_primary=data.get("font_primary", _NOTO_JP),
        font_secondary=data.get("font_secondary", _INTER),
        line_width_scale=float(data.get("line_width_scale", 1.0)),
        contrast=float(data.get("contrast", 1.0)),
        paper_texture=bool(data.get("paper_texture", False)),
    )


def _discover_bundled_themes() -> dict[str, Theme]:
    """Read every theme JSON file bundled under prettyplateau.assets.themes."""
    themes: dict[str, Theme] = {}
    try:
        root = files("prettyplateau.assets.themes")
        entries = list(root.iterdir())
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        fs_root = Path(__file__).resolve().parent.parent / "assets" / "themes"
        entries = list(fs_root.iterdir()) if fs_root.is_dir() else []
    for entry in entries:
        name = entry.name if hasattr(entry, "name") else str(entry)
        if not name.lower().endswith(".json"):
            continue
        theme = _load_theme_file(Path(str(entry)))
        themes[theme.id] = theme
    return themes


_THEMES: dict[str, Theme] = _discover_bundled_themes()


def get_theme(theme_id: str = "default") -> Theme:
    """Return a registered theme; falls back to 'default' on unknown id."""
    return _THEMES.get(theme_id, _THEMES.get("default", next(iter(_THEMES.values()))))


def list_themes() -> list[Theme]:
    return list(_THEMES.values())


def register_theme(theme: Theme) -> None:
    """Register a runtime theme (e.g. from a community entry point)."""
    _THEMES[theme.id] = theme


def with_palette(theme: Theme, palette: dict[str, str]) -> Theme:
    """Attach a preset-supplied palette to a theme copy."""
    merged = {**theme.palette, **palette}
    return replace(theme, palette=merged)

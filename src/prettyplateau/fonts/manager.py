"""Font wiring.

We bundle Noto Sans JP (OFL, redistributable) so renders look identical
across machines that may or may not have Japanese fonts installed at the
system level. Matplotlib resolves a font_family list left-to-right when a
glyph is missing, so we set the CJK font as a *fallback* on the global
font list rather than picking it per-text — that way both Latin titles and
Japanese legend entries render correctly without per-call branching.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path

from matplotlib import font_manager, rcParams

from prettyplateau.core.logging import get_logger

_logger = get_logger("fonts")

# Bundled OTF reports its family as "Noto Sans CJK JP" — we use whichever of
# the standard Noto names matplotlib actually sees after registration.
_CANDIDATE_JP_FAMILIES = ("Noto Sans JP", "Noto Sans CJK JP", "Noto Sans CJK")
JAPANESE_FONT_FAMILY = "Noto Sans CJK JP"
LATIN_FONT_FAMILY = "Inter"

_REGISTERED = False
_REGISTERED_NAMES: set[str] = set()


# Characters whose presence forces Japanese-capable font selection. We don't
# attempt to be exhaustive — a single CJK character is enough to switch.
_CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x3000, 0x303F),  # CJK Symbols and Punctuation
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xFF00, 0xFFEF),  # Halfwidth/Fullwidth forms
)


def _contains_japanese(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= code <= hi:
                return True
    return False


def resolve_text_font(text: str) -> str:
    """Return the font family that should be used to render `text`.

    Plan: "包含日文字符时返回 Noto Sans JP. 纯英文标题可返回 Inter."

    The returned family must exist in matplotlib's font manager. If the
    bundled Japanese font is registered we use it for any CJK-containing
    text; otherwise we use the Latin family. Callers can then pass the
    result to `Text.set_family()`.
    """
    register_bundled_fonts()
    if _contains_japanese(text):
        for cand in _CANDIDATE_JP_FAMILIES:
            if cand in _REGISTERED_NAMES:
                return cand
    if LATIN_FONT_FAMILY in _REGISTERED_NAMES:
        return LATIN_FONT_FAMILY
    # Fall back to whatever the global default is.
    return rcParams.get("font.sans-serif", ["sans-serif"])[0]


def _bundled_font_paths() -> Iterable[Path]:
    # `importlib.resources.files()` returns a MultiplexedPath that can't be
    # listed directly across all Python versions; iterate via iterdir() on
    # the underlying Traversable and fall back to a filesystem path probe
    # in the editable-install case where the dir might not be a package.
    try:
        root = files("prettyplateau.fonts.assets")
        entries = list(root.iterdir())
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        # Fall back to scanning the source tree next to this module.
        fs_root = Path(__file__).resolve().parent / "assets"
        if not fs_root.is_dir():
            return ()
        entries = list(fs_root.iterdir())  # type: ignore[assignment]
    out: list[Path] = []
    for entry in entries:
        name = entry.name if hasattr(entry, "name") else str(entry)
        if name.lower().endswith((".otf", ".ttf", ".ttc")):
            out.append(Path(str(entry)))
    return out


def register_bundled_fonts() -> None:
    """Idempotently add bundled fonts to matplotlib's font manager.

    Safe to call from `__init__.py`: subsequent calls are no-ops. If no
    bundled fonts are present (e.g. development checkout without the assets
    pulled in), the call still completes and matplotlib falls back to
    whatever the OS provides.
    """
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True

    registered_names: set[str] = set()
    for path in _bundled_font_paths():
        try:
            font_manager.fontManager.addfont(str(path))
            registered_names.add(font_manager.FontProperties(fname=str(path)).get_name())
        except Exception as exc:  # noqa: BLE001 — purely cosmetic; never block render
            _logger.warning("could not register font %s: %s", path.name, exc)
    _REGISTERED_NAMES.update(registered_names)

    if not registered_names:
        return

    # Prepend the bundled families to the global font.sans-serif fallback list so
    # CJK glyphs resolve against Noto Sans JP automatically, while Latin text
    # keeps its existing fallback chain. We don't *override* the user's choice
    # — we just add to the head.
    existing = list(rcParams.get("font.sans-serif", []))
    # Promote any Japanese/Noto family that registered successfully to the
    # head of the fallback chain so CJK glyphs resolve before matplotlib's
    # default DejaVu (which has no kanji).
    head: list[str] = []
    for cand in _CANDIDATE_JP_FAMILIES:
        if cand in registered_names and cand not in head:
            head.append(cand)
    if LATIN_FONT_FAMILY in registered_names:
        head.append(LATIN_FONT_FAMILY)
    rcParams["font.sans-serif"] = [*head, *[f for f in existing if f not in head]]
    rcParams["font.family"] = "sans-serif"
    _logger.info(
        "registered bundled fonts: %s; sans-serif head: %s",
        sorted(registered_names),
        head,
    )

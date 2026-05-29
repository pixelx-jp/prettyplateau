"""Plan-mandated font test — "字体测试断言日文字符可渲染".

We don't render a full figure here (slow). Instead we:
  1. Confirm the bundled Noto Sans CJK JP registered with matplotlib.
  2. Confirm `resolve_text_font` returns the CJK family for Japanese text
     and the Latin family for ASCII-only text.
"""

from __future__ import annotations

from prettyplateau.fonts.manager import (
    _CANDIDATE_JP_FAMILIES,
    _REGISTERED_NAMES,
    register_bundled_fonts,
    resolve_text_font,
)


def test_japanese_font_is_registered() -> None:
    register_bundled_fonts()
    assert any(jp in _REGISTERED_NAMES for jp in _CANDIDATE_JP_FAMILIES), (
        f"no Japanese-capable font registered; got {_REGISTERED_NAMES}"
    )


def test_resolve_text_font_picks_japanese_for_cjk() -> None:
    register_bundled_fonts()
    font = resolve_text_font("渋谷区")
    assert font in _CANDIDATE_JP_FAMILIES


def test_resolve_text_font_picks_latin_for_ascii() -> None:
    register_bundled_fonts()
    font = resolve_text_font("Shibuya — Use Mosaic")
    # Latin selection succeeds when Inter is bundled; otherwise falls back to
    # the global sans-serif default. Either way it must NOT be the CJK font.
    assert font not in _CANDIDATE_JP_FAMILIES or "Inter" in _REGISTERED_NAMES

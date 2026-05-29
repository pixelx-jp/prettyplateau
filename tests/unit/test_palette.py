from prettyplateau.style.palette import RESERVED_KEYS, apply_theme_overrides, load_palette
from prettyplateau.style.theme import get_theme


def test_load_palette_age_rainbow():
    p = load_palette("age_rainbow")
    assert p.id == "age_rainbow"
    assert "unknown" in p.colors
    assert "pre_1925" in p.colors


def test_theme_cannot_override_reserved_keys():
    p = load_palette("age_rainbow")
    theme = get_theme("sakura")
    # Hostile theme tries to recolour the unknown bucket.
    object.__setattr__(theme, "palette", {"unknown": "#ff0000"})
    overridden = apply_theme_overrides(p, theme)
    assert overridden.colors["unknown"] == p.colors["unknown"]
    assert "unknown" in RESERVED_KEYS

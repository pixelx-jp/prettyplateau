"""Sanity tests for the preset registry and metadata invariants."""

from __future__ import annotations

import pytest

from prettyplateau import list_presets
from prettyplateau.core.errors import PresetNotFoundError
from prettyplateau.presets.registry import get_registry


def test_builtins_registered():
    ids = {m.id for m in list_presets()}
    assert {"age_rainbow", "use_mosaic", "wood_survivor"}.issubset(ids)


def test_resolve_kebab_or_snake():
    reg = get_registry()
    a = reg.resolve("age_rainbow")
    b = reg.resolve("age-rainbow")
    assert type(a) is type(b)


def test_unknown_preset_raises():
    with pytest.raises(PresetNotFoundError):
        get_registry().resolve("does_not_exist")


def test_no_preset_lacks_required_fields():
    for meta in list_presets():
        assert meta.id
        assert meta.modes
        assert meta.required_fields  # every built-in preset must declare its needs


def test_attribution_text_appears_in_every_preset_metadata():
    # The attribution string itself isn't on the preset, but its description must
    # never claim that no-data buildings have any meaningful colour.
    for meta in list_presets():
        assert "low risk" not in meta.description.lower()

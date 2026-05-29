"""Unit tests for the prebuilt-bundle fetch resolver (no network)."""

from __future__ import annotations

import json

import pytest

from prettyplateau.data.fetch import (
    FetchError,
    _slugify_city_name,
    load_index,
    resolve_entry,
)

_INDEX = {
    "schema": 1,
    "cities": [
        {
            "city_code": "13101",
            "city_name": "Chiyoda-ku",
            "dataset_year": 2023,
            "bundle_url": "https://example/plateau-13101-2023-v1.tar.zst",
            "sha256": "a" * 64,
            "bytes": 100,
            "n_buildings": 12541,
        },
        {
            "city_code": "13113",
            "city_name": "Shibuya-ku",
            "dataset_year": 2023,
            "bundle_url": "https://example/plateau-13113-2023-v1.tar.zst",
            "sha256": "b" * 64,
            "bytes": 200,
            "n_buildings": 41858,
        },
        {
            "city_code": "27100",
            "city_name": "Osaka-shi",
            "dataset_year": 2024,
            "bundle_url": "https://example/plateau-27100-2024-v1.tar.zst",
            "sha256": "c" * 64,
            "bytes": 300,
            "n_buildings": 999,
        },
    ],
}


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Chiyoda-ku", "chiyoda"), ("Osaka-shi", "osaka"), ("Sapporo-shi", "sapporo"), ("Foo", "foo")],
)
def test_slugify_city_name(name: str, expected: str) -> None:
    assert _slugify_city_name(name) == expected


@pytest.fixture
def index_url(tmp_path):
    p = tmp_path / "index.json"
    p.write_text(json.dumps(_INDEX), encoding="utf-8")
    return f"file://{p}"


def test_load_index_typed_and_sorted(index_url: str) -> None:
    entries = load_index(index_url)
    assert {e.slug for e in entries} == {"chiyoda", "shibuya", "osaka"}
    # newest dataset_year first
    assert entries[0].dataset_year == 2024
    assert entries[0].slug == "osaka"


def test_resolve_by_jis_code(index_url: str) -> None:
    e = resolve_entry("13113", load_index(index_url))
    assert e.city_name == "Shibuya-ku"


def test_resolve_by_slug(index_url: str) -> None:
    e = resolve_entry("shibuya", load_index(index_url))
    assert e.city_code == "13113"


def test_resolve_via_alias_table(index_url: str) -> None:
    # CITY_ALIASES maps "chiyoda" → ("chiyoda", "chiyoda-ku"); both slugify back.
    e = resolve_entry("Chiyoda", load_index(index_url))
    assert e.city_code == "13101"


def test_resolve_unknown_city_lists_available(index_url: str) -> None:
    with pytest.raises(FetchError) as exc:
        resolve_entry("kyoto", load_index(index_url))
    msg = str(exc.value)
    assert "kyoto" in msg
    assert "chiyoda" in msg and "shibuya" in msg and "osaka" in msg

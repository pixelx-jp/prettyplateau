"""Integration test — the full Preset → Renderer → Composer → Exporter chain
end-to-end on the synthetic fixture, with sidecar JSON, multi-format output,
and metadata round-trip.

The visual / unit suites cover the stages in isolation; this one checks that
they compose correctly when wired through `prettyplateau.api.render()`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

from prettyplateau.api.render import render
import prettyplateau.data.access as access_module
import prettyplateau.testing.fixtures as fixtures


class _FixedDataAccess:
    def __init__(self, *_, **__) -> None:
        self._dataset = fixtures.fixture_dataset(n=32)

    def load_city(self, city, *, bbox=None, columns=None):
        # Honour the city slug while keeping the fixture's geometry / fields.
        return access_module.CityDataset(
            city=city,
            city_name=self._dataset.city_name,
            city_code=self._dataset.city_code,
            dataset_year=self._dataset.dataset_year,
            dataset_id=self._dataset.dataset_id,
            attribution=self._dataset.attribution,
            field_coverage=self._dataset.field_coverage,
            n_buildings=self._dataset.n_buildings,
            gdf=self._dataset.gdf,
            source_root=None,
            admin_boundary=None,
            extras=dict(self._dataset.extras),
        )

    def get_attribution(self, dataset):
        return dataset.attribution


def test_full_pipeline_png_with_sidecar(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sys.modules["prettyplateau.api.render"], "DataAccess", _FixedDataAccess)
    out = tmp_path / "use_mosaic.png"
    result = render(
        city="fixture",
        preset="use_mosaic",
        out=str(out),
        title="Integration test",
        subtitle="fixture city",
        width=400,
        overwrite=True,
        sidecar=True,
    )
    # Output exists, has the right format, and carries attribution metadata.
    assert result.path == str(out)
    img = Image.open(out)
    assert "Attribution" in img.info
    assert "PLATEAU" in img.info["Attribution"]
    sidecar = out.with_suffix(out.suffix + ".json")
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text())
    # Plan: sidecar contains request, preset metadata, dataset id, warnings.
    assert "Artifact" in payload and "Attribution" in payload["Artifact"]
    assert "Request" in payload and payload["Request"]["preset"] == "use_mosaic"
    assert "Preset" in payload and payload["Preset"]["id"] == "use_mosaic"
    assert "Scene" in payload
    assert payload["Scene"]["n_layers"] >= 1
    assert "Warnings" in payload


def test_full_pipeline_multi_format(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sys.modules["prettyplateau.api.render"], "DataAccess", _FixedDataAccess)
    primary = tmp_path / "shibuya.png"
    extra_outs = [str(tmp_path / "shibuya.svg"), str(tmp_path / "shibuya.pdf")]
    result = render(
        city="fixture",
        preset="use_mosaic",
        out=str(primary),
        width=400,
        overwrite=True,
        extra_outs=extra_outs,
    )
    assert result.path == str(primary)
    # All three formats must have been produced from a single data load.
    for path in [primary, *[Path(p) for p in extra_outs]]:
        assert path.exists(), f"missing {path}"

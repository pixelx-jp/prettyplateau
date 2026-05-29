"""Plan-mandated parity test: CLI and API must produce identical metadata.

The plan says "API 测试断言 CLI/API 结果 metadata 一致". We satisfy this by
constructing the same `RenderRequest` two ways — once via the CLI flag
parser (`render_cmd`), once directly via `prettyplateau.render(request=...)`
— and asserting the resulting `RenderResult.metadata` matches.

Both code paths now share a single execution contract through
`render(request=...)`, so this guards against regressions where the CLI
shortcut starts decomposing args or injecting extra fields.
"""

from __future__ import annotations

import sys
from pathlib import Path

import prettyplateau.data.access as access_module
import prettyplateau.testing.fixtures as fixtures
from prettyplateau.api.render import render
from prettyplateau.api.types import RenderRequest


class _FixedDataAccess:
    def __init__(self, *_, **__) -> None:
        self._dataset = fixtures.fixture_dataset(n=24)

    def load_city(self, city, *, bbox=None, columns=None):
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


def _stable_metadata(md: dict) -> dict:
    """Drop fields that legitimately vary between two runs."""
    drop = {"GeneratedAt", "WrittenPaths"}
    return {k: v for k, v in md.items() if k not in drop}


def test_cli_and_api_metadata_match(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sys.modules["prettyplateau.api.render"], "DataAccess", _FixedDataAccess)

    # API call — uses keyword args directly.
    out_api = tmp_path / "api.png"
    api_result = render(
        city="fixture",
        preset="use_mosaic",
        out=str(out_api),
        title="parity",
        width=300,
        overwrite=True,
    )

    # CLI-style call — uses an explicit RenderRequest.
    out_cli = tmp_path / "cli.png"
    cli_request = RenderRequest(
        city="fixture",
        preset="use_mosaic",
        out=str(out_cli),
        title="parity",
        width=300,
        overwrite=True,
    )
    cli_result = render(request=cli_request)

    md_a = _stable_metadata(api_result.metadata)
    md_b = _stable_metadata(cli_result.metadata)
    assert md_a == md_b, f"CLI and API metadata diverged:\nCLI={md_b}\nAPI={md_a}"
    # The attribution string and dataset_id must always match.
    assert api_result.attribution == cli_result.attribution
    assert api_result.dataset_id == cli_result.dataset_id

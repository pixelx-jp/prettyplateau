"""Verify the `out=None` and `return_scene=True` code paths.

Plan: "若 `out=None`，静图可返回 PIL Image 或 matplotlib Figure" and
"若 `return_scene=True`，高级用户可获取 `RenderScene`".
"""

from __future__ import annotations

from matplotlib.figure import Figure

import prettyplateau.data.access as access_module
import prettyplateau.testing.fixtures as fixtures
from prettyplateau.api.render import render
from prettyplateau.presets.scene import RenderScene


class _FixedDataAccess:
    """Replacement adapter that always returns the synthetic fixture.

    Bypasses disk + plateau_bridge so the tests are fast and hermetic.
    """

    def __init__(self, *_, **__) -> None:
        self._dataset = fixtures.fixture_dataset(n=24)

    def load_city(self, city, *, bbox=None, columns=None):
        # Honour the city slug for accurate metadata in the result.
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
            source_root=self._dataset.source_root,
            admin_boundary=None,
            extras=dict(self._dataset.extras),
        )

    def get_attribution(self, dataset):
        return dataset.attribution


def test_out_none_returns_figure(monkeypatch):
    # The `render` function imports `DataAccess` at module load time. Patch
    # the symbol in `prettyplateau.api.render`'s namespace (which is what the
    # function resolves at call time), accessed via sys.modules to avoid
    # the name-collision with the `render()` function.
    import sys

    render_module = sys.modules["prettyplateau.api.render"]
    monkeypatch.setattr(render_module, "DataAccess", _FixedDataAccess)
    result = render(city="fixture", preset="use_mosaic", out=None, width=400)
    assert result.path is None
    assert isinstance(result.figure, Figure)
    assert result.scene is None  # not requested
    assert result.width > 0 and result.height > 0
    assert "PLATEAU" in result.attribution


def test_return_scene_true(monkeypatch):
    import sys

    render_module = sys.modules["prettyplateau.api.render"]
    monkeypatch.setattr(render_module, "DataAccess", _FixedDataAccess)
    result = render(city="fixture", preset="use_mosaic", out=None, return_scene=True, width=400)
    assert isinstance(result.scene, RenderScene)
    assert result.scene.layers
    assert "PLATEAU" in result.attribution

"""Preset registry — built-ins register on import; third parties via entry points."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Callable

from prettyplateau.api.types import PresetMetadata
from prettyplateau.core.errors import PresetNotFoundError
from prettyplateau.core.logging import get_logger
from prettyplateau.presets.base import BasePreset

_logger = get_logger("registry")


PresetFactory = Callable[[], BasePreset]


class PresetRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, PresetFactory] = {}
        self._metadata: dict[str, PresetMetadata] = {}
        self._builtin_ids: set[str] = set()
        self._loaded_entry_points: bool = False

    def register(
        self,
        factory: PresetFactory,
        *,
        metadata: PresetMetadata,
        builtin: bool = False,
    ) -> None:
        pid = metadata.id
        if pid in self._builtin_ids and not builtin:
            raise ValueError(f"refusing to override built-in preset {pid!r}")
        self._factories[pid] = factory
        self._metadata[pid] = metadata
        if builtin:
            self._builtin_ids.add(pid)

    def resolve(self, preset_id: str) -> BasePreset:
        self._load_entry_points()
        if preset_id not in self._factories:
            # Tolerate kebab/snake mix.
            alt = preset_id.replace("-", "_")
            if alt in self._factories:
                preset_id = alt
            else:
                raise PresetNotFoundError(
                    f"preset {preset_id!r} not found; known: {sorted(self._factories)}"
                )
        try:
            return self._factories[preset_id]()
        except Exception as exc:
            raise PresetNotFoundError(
                f"preset {preset_id!r} failed to instantiate: {exc}"
            ) from exc

    def list_metadata(self) -> list[PresetMetadata]:
        self._load_entry_points()
        return [self._metadata[k] for k in sorted(self._metadata)]

    def _load_entry_points(self) -> None:
        if self._loaded_entry_points:
            return
        self._loaded_entry_points = True
        try:
            eps = entry_points(group="prettyplateau.presets")
        except TypeError:  # older importlib API shape
            eps = entry_points().get("prettyplateau.presets", [])  # type: ignore[attr-defined]
        for ep in eps:
            try:
                obj = ep.load()
                preset = obj() if callable(obj) else obj
                if not isinstance(preset, BasePreset):
                    _logger.warning("entry point %r did not yield a BasePreset", ep.name)
                    continue
                self.register(obj if callable(obj) else (lambda p=preset: p), metadata=preset.metadata)
            except Exception:  # noqa: BLE001
                _logger.exception("failed to load preset entry point %r", ep.name)


_registry: PresetRegistry | None = None


def get_registry() -> PresetRegistry:
    global _registry
    if _registry is None:
        _registry = PresetRegistry()
        _register_builtins(_registry)
    return _registry


def _register_builtins(reg: PresetRegistry) -> None:
    # Imported lazily to avoid cycles with the registry module itself.
    from prettyplateau.presets import (  # noqa: WPS433 — intentional lazy import
        age_rainbow,
        density_hex,
        flood_depth,
        hazard_confluence,
        height_topo,
        risk_choropleth,
        survivor_timeline,
        use_mosaic,
        wood_survivor,
        zoning_mosaic,
    )

    for module in (
        age_rainbow,
        wood_survivor,
        use_mosaic,
        risk_choropleth,
        flood_depth,
        height_topo,
        survivor_timeline,
        hazard_confluence,
        density_hex,
        zoning_mosaic,
    ):
        preset = module.PRESET
        reg.register(module.factory, metadata=preset.metadata, builtin=True)

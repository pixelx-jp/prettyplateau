"""Compatibility re-export of the preset registry.

The plan-prettyplateau.md package layout places the registry under `core/`.
The implementation lives in `prettyplateau.presets.registry` (so registry
helpers and preset classes can co-locate). This module exists as a re-export
so external callers can use either path:

    from prettyplateau.core.registry import get_registry  # plan-shaped path
    from prettyplateau.presets.registry import get_registry  # implementation path

Both resolve to the same singleton.
"""

from __future__ import annotations

from prettyplateau.presets.registry import (
    PresetFactory,
    PresetRegistry,
    get_registry,
)

__all__ = ["PresetRegistry", "PresetFactory", "get_registry"]

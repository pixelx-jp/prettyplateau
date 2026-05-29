"""Compatibility re-exports for the attribution string from manifests.

Plan layout places attribution-reading helpers under `_core_lite/attribution.py`.
The actual logic lives in `_core_lite/loader.py::LiteManifest`; this module
re-exports the manifest type and a small helper for callers who only need
the attribution string.
"""

from __future__ import annotations

from pathlib import Path

from prettyplateau._core_lite.loader import LiteManifest, load_manifest


def read_attribution(root: Path) -> str:
    """Read the attribution string for a `out_<city>/` directory."""
    manifest: LiteManifest = load_manifest(root)
    return manifest.attribution


__all__ = ["LiteManifest", "load_manifest", "read_attribution"]

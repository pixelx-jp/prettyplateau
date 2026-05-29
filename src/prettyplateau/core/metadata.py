"""Artifact metadata helpers — shared by every exporter so the keys stay aligned."""

from __future__ import annotations

import datetime as _dt
from typing import Any

from prettyplateau._version import __version__


def build_artifact_metadata(
    *,
    preset_id: str,
    city: str,
    dataset_id: str | None,
    attribution: str,
    theme: str,
    generated_at: _dt.datetime | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, str]:
    when = generated_at or _dt.datetime.now(tz=_dt.timezone.utc)
    md: dict[str, str] = {
        "Software": f"prettyplateau {__version__}",
        "Attribution": attribution,
        "Preset": preset_id,
        "City": city,
        "Theme": theme,
        "GeneratedAt": when.replace(microsecond=0).isoformat(),
    }
    if dataset_id:
        md["DatasetID"] = dataset_id
    if extra:
        for k, v in extra.items():
            md[str(k)] = str(v)
    return md

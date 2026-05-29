"""Legend helpers — semantic key → display label mapping.

The composer draws the legend; this module owns label formatting so
the same swatch never gets two different captions across presets.
"""

from __future__ import annotations


# Canonical labels for reserved palette keys. Presets can override per
# legend entry, but if they don't these defaults keep the language stable.
RESERVED_LABELS: dict[str, str] = {
    "unknown": "Unknown / no data",
    "no_data": "No data",
}


def label_for(key: str, default: str | None = None) -> str:
    if key in RESERVED_LABELS:
        return RESERVED_LABELS[key]
    return default or key.replace("_", " ").title()

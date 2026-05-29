"""Attribution → GLB asset extras helper.

The plan reserves the right to add 3D output later: "v1 不承诺 GLB 导出。
但 attribution 数据模型预留 `to_glb_extras()`". This module implements that
forward-looking surface without requiring `pygltflib` at install time.

When a future `GLBExporter` ships, it consumes the dict produced here and
writes it to `asset.extras` per the glTF 2.0 spec.
"""

from __future__ import annotations

from typing import Any

from prettyplateau.compose.attribution_injector import AttributionSpec


def to_glb_extras(spec: AttributionSpec, *, license_url: str = "https://creativecommons.org/licenses/by/4.0/") -> dict[str, Any]:
    """Render an AttributionSpec into a glTF `asset.extras` dictionary.

    Per the plan, the dict must include at minimum:
      - attribution (visible string)
      - dataset_id
      - license (URL or SPDX-style id)
      - generated_at (ISO8601)

    GLB consumers SHOULD honour the visible attribution in their UI; the
    `extras` payload is not an opt-out for visible attribution in derived
    artifacts.
    """
    return {
        "attribution": spec.primary_line(),
        "dataset_id": spec.dataset_id,
        "license": license_url,
        "generated_at": spec.generated_at.replace(microsecond=0).isoformat(),
    }

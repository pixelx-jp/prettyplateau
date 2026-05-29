"""Plan-mandated mp4 attribution contract — `VideoExporter.write_frames`
must REJECT calls that omit the attribution card or the PLATEAU metadata
string. This guards against a future caller accidentally producing an
mp4 that ships without visible attribution.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from prettyplateau.core.errors import AttributionError
from prettyplateau.export.video import VideoExporter


def _stub_frames() -> list[np.ndarray]:
    # Two frames, even dimensions so libx264 doesn't reject them. Content
    # doesn't matter — we never reach the encoder in failure paths.
    frame = np.full((20, 20, 4), 255, dtype=np.uint8)
    return [frame, frame]


def test_mp4_refuses_to_encode_without_attribution_card(tmp_path: Path) -> None:
    exporter = VideoExporter()
    with pytest.raises(AttributionError):
        exporter.write_frames(
            tmp_path / "bad.mp4",
            frames=iter(_stub_frames()),
            fps=2,
            metadata={"Attribution": "© Project PLATEAU / MLIT (CC BY 4.0)"},
            attribution_card=None,  # type: ignore[arg-type]
        )


def test_mp4_refuses_to_encode_with_empty_attribution_string(tmp_path: Path) -> None:
    exporter = VideoExporter()
    with pytest.raises(AttributionError):
        exporter.write_frames(
            tmp_path / "bad.mp4",
            frames=iter(_stub_frames()),
            fps=2,
            metadata={"Attribution": ""},  # missing PLATEAU
            attribution_card=np.full((20, 20, 4), 255, dtype=np.uint8),
        )

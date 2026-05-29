"""Plan-mandated mp4 test: "读取最后几帧，断言 attribution card 存在".

Approach: render a small synthetic mp4, decode it, sample the last frames,
and check they look meaningfully different from the main timeline frames
(the attribution card is a stop-frame snapshot, not part of the moving
timeline). We don't OCR the card text — the metadata test already covers
that — but we do verify the encoder honoured the attribution_card argument
by producing a stretch of duplicated frames at the end.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

import prettyplateau.data.access as access_module
import prettyplateau.testing.fixtures as fixtures
from prettyplateau.api.render import render


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


def test_mp4_ends_with_attribution_card(tmp_path: Path, monkeypatch) -> None:
    """Read the last N frames of a freshly-encoded mp4 and assert they are
    the attribution card.

    The card frames are identical (a frozen snapshot of the final composed
    figure repeated for ~2 seconds). The main timeline frames mutate building
    fills between frames. So the diagnostic is simple: the final-N frames
    should be byte-identical to each other AND visibly different from a frame
    sampled from earlier in the video.
    """
    try:
        import imageio.v3 as iio  # noqa: F401
        import imageio_ffmpeg  # noqa: F401
    except ImportError:
        pytest.skip("imageio[ffmpeg] not installed; mp4 round-trip skipped")

    monkeypatch.setattr(sys.modules["prettyplateau.api.render"], "DataAccess", _FixedDataAccess)
    out_mp4 = tmp_path / "fixture_timeline.mp4"
    render(
        city="fixture",
        preset="survivor_timeline",
        out=str(out_mp4),
        width=400,
        overwrite=True,
        # Keep the test fast: 6 timeline frames at 3 fps, 2s of attribution card.
        frames=6,
        fps=3,
    )
    assert out_mp4.exists() and out_mp4.stat().st_size > 0

    import imageio.v3 as iio

    video = iio.imread(out_mp4, plugin="FFMPEG")  # shape (N, H, W, 3)
    assert video.ndim == 4 and video.shape[0] >= 4, f"video has {video.shape}, expected ≥4 frames"

    # Last frames should be near-identical (the attribution card is a still,
    # but H.264 macroblock noise may add ~1-2 LSB of jitter between repeated
    # copies, so we use a small threshold rather than exact byte equality).
    last = video[-1]
    second_last = video[-2]
    card_internal_diff = np.abs(last.astype(int) - second_last.astype(int)).mean()
    assert card_internal_diff < 1.0, (
        f"attribution card frames diverge by mean {card_internal_diff:.3f}; "
        f"expected a still — h264 noise should be < 1 LSB per pixel"
    )

    # And they should differ meaningfully from a mid-video frame (otherwise
    # the whole video is the same still and we wouldn't be testing what we
    # think).
    mid = video[len(video) // 2]
    if mid.shape == last.shape:
        timeline_vs_card_diff = np.abs(mid.astype(int) - last.astype(int)).mean()
        assert timeline_vs_card_diff > card_internal_diff * 2 or timeline_vs_card_diff > 0.5, (
            f"mid-video frame and final card frame too similar (mean diff "
            f"{timeline_vs_card_diff:.3f} vs card-internal {card_internal_diff:.3f}); "
            f"the card may not be appended"
        )

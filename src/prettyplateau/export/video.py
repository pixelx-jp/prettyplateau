"""mp4 exporter via imageio-ffmpeg.

Plan contract:
- "mp4 正片帧不强制每帧显示完整 attribution"  — per-frame attribution corner is
  drawn by the composer; not enforced here.
- "视频末尾必须追加 1-2 秒 attribution card" — mandatory.
- "container metadata 写入 attribution" — mandatory.
- "moviepy 帧生成采用 generator，避免一次性存满内存" — mandatory.

Both attribution requirements are enforced by THIS module raising on missing
inputs, rather than the caller; that way no future code path can ship a
non-compliant mp4 by accidentally passing `attribution_card=None`.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import numpy as np

from prettyplateau.compose.composer import ComposedArtifact
from prettyplateau.core.errors import AttributionError, ExportError
from prettyplateau.export.base import ExportResult


def _require_imageio():
    try:
        import imageio  # noqa: F401
        import imageio_ffmpeg  # noqa: F401
    except ImportError as exc:
        raise ExportError(
            "mp4 export requires `prettyplateau[animation]` (imageio + imageio-ffmpeg). "
            "Install via: pip install 'prettyplateau[animation]'"
        ) from exc


def _crop_to_even(rgb: np.ndarray) -> np.ndarray:
    """libx264 + yuv420p chroma subsampling requires even dimensions; crop one
    pixel off if necessary. Invisible at 1080p+ and avoids `height must be
    even` errors from ffmpeg."""
    h, w, _ = rgb.shape
    if h % 2 == 1:
        rgb = rgb[: h - 1, :, :]
    if rgb.shape[1] % 2 == 1:
        rgb = rgb[:, : rgb.shape[1] - 1, :]
    return rgb


def _pad_to_shape(rgb: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    """Pad / crop a card frame so it matches the main video resolution."""
    if rgb.shape == shape:
        return rgb
    pad = np.full(shape, 255, dtype=np.uint8)
    h = min(shape[0], rgb.shape[0])
    w = min(shape[1], rgb.shape[1])
    pad[:h, :w] = rgb[:h, :w]
    return pad


class VideoExporter:
    format = "mp4"

    def write(
        self,
        artifact: ComposedArtifact,
        out_path: Path,
        *,
        metadata: dict[str, str],
        overwrite: bool = False,
    ) -> ExportResult:
        raise ExportError(
            "VideoExporter.write requires a frame stream; call write_frames() instead."
        )

    def write_frames(
        self,
        out_path: Path,
        *,
        frames: Iterable[np.ndarray],
        fps: int,
        metadata: dict[str, str],
        attribution_card: np.ndarray,
        attribution_card_seconds: float = 2.0,
        overwrite: bool = False,
    ) -> ExportResult:
        # Plan-mandated compliance: every mp4 prettyplateau emits MUST carry a
        # final attribution card AND container metadata. Both inputs are
        # required and validated *before* we open the encoder so failure is
        # fail-fast with no partial mp4 on disk.
        if attribution_card is None or attribution_card.size == 0:
            raise AttributionError(
                "mp4 export requires a non-empty attribution_card; refusing to encode."
            )
        attribution_text = metadata.get("Attribution") or ""
        if "PLATEAU" not in attribution_text:
            raise AttributionError(
                f"mp4 metadata missing valid PLATEAU attribution string (got {attribution_text!r})."
            )

        _require_imageio()
        import imageio_ffmpeg

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and not overwrite:
            raise ExportError(f"{out_path} exists; pass overwrite=True to replace")

        n_card = max(int(round(fps * attribution_card_seconds)), 1)
        # Stream frames lazily to the encoder so we never hold all of them in
        # memory at once. The first frame is also used to pin the canvas size
        # — all subsequent frames (incl. the card) are cropped/padded to match.
        def stream() -> Iterator[np.ndarray]:
            first_shape: tuple[int, int, int] | None = None
            n_main = 0
            for rgba in frames:
                rgb = _crop_to_even(rgba[..., :3])
                if first_shape is None:
                    first_shape = rgb.shape
                elif rgb.shape != first_shape:
                    rgb = rgb[: first_shape[0], : first_shape[1], :]
                n_main += 1
                yield rgb
            if first_shape is None:
                raise ExportError("no frames produced by the animator")
            # Mandatory final attribution card.
            card = _crop_to_even(attribution_card[..., :3])
            card = _pad_to_shape(card, first_shape)
            for _ in range(n_card):
                yield card
            # Stash the first-frame shape for the caller via a closure cell.
            stream.first_shape = first_shape  # type: ignore[attr-defined]
            stream.n_frames = n_main + n_card  # type: ignore[attr-defined]

        imageio_ffmpeg.get_ffmpeg_exe()
        # Probe a single frame to learn the shape — `frames` is a generator,
        # so we tee one item. Simplest: read once, then chain it back into
        # the encoder feed.
        gen = stream()
        try:
            first = next(gen)
        except StopIteration:
            raise ExportError("no frames produced by the animator") from None
        h, w = first.shape[:2]
        writer = imageio_ffmpeg.write_frames(
            str(out_path),
            (w, h),
            fps=float(fps),
            macro_block_size=1,
            codec="libx264",
            pix_fmt_in="rgb24",
            pix_fmt_out="yuv420p",
            output_params=[
                "-movflags", "+faststart",
                "-metadata", f"comment={attribution_text}",
                "-metadata", f"title={metadata.get('Preset', 'prettyplateau')}",
                "-metadata", f"artist={metadata.get('Software', 'prettyplateau')}",
                "-metadata", f"copyright={attribution_text}",
                "-metadata", f"description={metadata.get('DatasetID', '')}",
            ],
            ffmpeg_log_level="warning",
        )
        writer.send(None)  # initialise generator
        try:
            writer.send(first.tobytes())
            for frame in gen:
                writer.send(frame.tobytes())
        finally:
            writer.close()

        return ExportResult(
            path=out_path,
            width=w,
            height=h,
            metadata=metadata,
        )


# Convenience for the api.render layer to know whether to dispatch through here.
def is_animation_format(fmt: str) -> bool:
    return fmt == "mp4"

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, PngImagePlugin

from prettyplateau.compose.composer import ComposedArtifact
from prettyplateau.core.errors import ExportError
from prettyplateau.export.base import ExportResult


class PNGExporter:
    format = "png"

    def write(
        self,
        artifact: ComposedArtifact,
        out_path: Path,
        *,
        metadata: dict[str, str],
        overwrite: bool = False,
    ) -> ExportResult:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and not overwrite:
            raise ExportError(f"{out_path} exists; pass overwrite=True to replace")

        # Round-trip through PIL so we can attach tEXt/iTXt metadata reliably.
        buf = io.BytesIO()
        artifact.figure.savefig(buf, format="png", dpi=artifact.figure.dpi)
        buf.seek(0)
        img = Image.open(buf)
        info = PngImagePlugin.PngInfo()
        for k, v in metadata.items():
            info.add_text(k, v)
        img.save(out_path, format="PNG", pnginfo=info, optimize=False)
        artifact.attribution_report.metadata = True
        artifact.attribution_report.require_visible_and_metadata()
        return ExportResult(path=out_path, width=img.width, height=img.height, metadata=metadata)

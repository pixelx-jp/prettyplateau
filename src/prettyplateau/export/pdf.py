from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages

from prettyplateau.compose.composer import ComposedArtifact
from prettyplateau.core.errors import ExportError
from prettyplateau.export.base import ExportResult


class PDFExporter:
    format = "pdf"

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

        with PdfPages(out_path, metadata=self._pdf_metadata(metadata)) as pdf:
            pdf.savefig(artifact.figure)

        artifact.attribution_report.metadata = True
        artifact.attribution_report.require_visible_and_metadata()
        # Width/height in pixels from figure (for reporting).
        w_in, h_in = artifact.figure.get_size_inches()
        dpi = artifact.figure.dpi
        return ExportResult(
            path=out_path,
            width=int(round(w_in * dpi)),
            height=int(round(h_in * dpi)),
            metadata=metadata,
        )

    def _pdf_metadata(self, md: dict[str, str]) -> dict[str, str]:
        # matplotlib's PdfPages accepts a fixed-ish set of keys: Title, Author,
        # Subject, Keywords, Producer, Creator, CreationDate, ModDate.
        return {
            "Title": md.get("Preset", "prettyplateau") + " — " + md.get("City", ""),
            "Author": md.get("Attribution", ""),
            "Subject": md.get("Attribution", ""),
            "Keywords": ",".join(
                v for v in (md.get("Preset"), md.get("Theme"), md.get("DatasetID")) if v
            ),
            "Creator": md.get("Software", "prettyplateau"),
            "Producer": md.get("Software", "prettyplateau"),
        }

from prettyplateau.export.base import Exporter, ExportResult
from prettyplateau.export.pdf import PDFExporter
from prettyplateau.export.png import PNGExporter
from prettyplateau.export.svg import SVGExporter

__all__ = ["Exporter", "ExportResult", "PNGExporter", "SVGExporter", "PDFExporter"]


def exporter_for_format(fmt: str) -> Exporter:
    fmt = fmt.lower()
    if fmt == "png":
        return PNGExporter()
    if fmt == "svg":
        return SVGExporter()
    if fmt == "pdf":
        return PDFExporter()
    if fmt == "mp4":
        from prettyplateau.export.video import VideoExporter

        return VideoExporter()
    raise ValueError(f"unknown output format: {fmt!r}")

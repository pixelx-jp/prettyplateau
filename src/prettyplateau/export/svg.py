from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from prettyplateau.compose.composer import ComposedArtifact
from prettyplateau.core.errors import ExportError
from prettyplateau.export.base import ExportResult


_SVG_NS = "http://www.w3.org/2000/svg"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_DC_NS = "http://purl.org/dc/elements/1.1/"


class SVGExporter:
    format = "svg"

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

        buf = io.BytesIO()
        artifact.figure.savefig(buf, format="svg")
        buf.seek(0)

        # Parse and inject metadata.
        ET.register_namespace("", _SVG_NS)
        ET.register_namespace("rdf", _RDF_NS)
        ET.register_namespace("dc", _DC_NS)
        tree = ET.parse(buf)
        root = tree.getroot()
        meta = ET.SubElement(root, f"{{{_SVG_NS}}}metadata")
        rdf = ET.SubElement(meta, f"{{{_RDF_NS}}}RDF")
        descr = ET.SubElement(rdf, f"{{{_RDF_NS}}}Description")
        for k, v in metadata.items():
            el = ET.SubElement(descr, f"{{{_DC_NS}}}{k}")
            el.text = v
        tree.write(out_path, xml_declaration=True, encoding="utf-8")

        artifact.attribution_report.metadata = True
        artifact.attribution_report.require_visible_and_metadata()
        # SVG size: best-effort from viewBox.
        vb = root.get("viewBox", "")
        try:
            _, _, w, h = (float(x) for x in vb.split())
            width, height = int(w), int(h)
        except Exception:  # noqa: BLE001
            width = height = 0
        return ExportResult(path=out_path, width=width, height=height, metadata=metadata)

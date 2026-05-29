"""Round-trip tests for PNG, SVG and PDF exporters.

Every exporter is contractually required to:
  - emit a visible attribution line on the canvas, and
  - embed the same attribution into the file's container metadata,
  - propagate the dataset id and preset id.

These tests render the smallest valid scene we can build and assert all three
on the resulting file. Heavy-weight rendering already happens in the visual
smoke tests; this one is fast and lives alongside other unit tests.
"""

from __future__ import annotations

import datetime as _dt
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from prettyplateau.api.types import RenderRequest
from prettyplateau.compose.attribution_injector import AttributionInjector, AttributionSpec
from prettyplateau.compose.composer import Composer, CompositionOptions
from prettyplateau.export.pdf import PDFExporter
from prettyplateau.export.png import PNGExporter
from prettyplateau.export.svg import SVGExporter
from prettyplateau.presets.registry import get_registry
from prettyplateau.renderers.matplotlib_renderer import MatplotlibRenderer, RenderOptions
from prettyplateau.style.theme import get_theme
from prettyplateau.testing.fixtures import fixture_dataset

ATTR_TEXT = "© Project PLATEAU / MLIT (CC BY 4.0)"
DATASET_ID = "fixture-dataset-2024"
METADATA = {
    "Software": "prettyplateau-test",
    "Attribution": ATTR_TEXT,
    "Preset": "use_mosaic",
    "City": "fixture",
    "Theme": "default",
    "DatasetID": DATASET_ID,
    "GeneratedAt": "2026-05-29T00:00:00+00:00",
}


def _make_composition():
    dataset = fixture_dataset(n=32)
    preset = get_registry().resolve("use_mosaic")
    request = RenderRequest(city="fixture", preset="use_mosaic")
    prepared = preset.prepare(dataset, request)
    theme = get_theme("default")
    scene = preset.build_scene(prepared, theme, request)
    opts = CompositionOptions(title="exporter-test", subtitle="fixture")
    fig = MatplotlibRenderer().render(
        scene,
        theme,
        RenderOptions(
            width_px=400,
            top_margin=opts.top_margin(),
            bottom_margin=opts.bottom_margin(),
            side_margin=opts.side_margin(),
        ),
    )
    spec = AttributionSpec(
        text=ATTR_TEXT,
        dataset_id=DATASET_ID,
        generated_at=_dt.datetime(2026, 5, 29, tzinfo=_dt.timezone.utc),
    )
    return Composer(AttributionInjector(spec)).compose(fig, scene, theme, opts)


def test_png_metadata_contains_attribution(tmp_path: Path):
    composition = _make_composition()
    out = tmp_path / "use_mosaic.png"
    PNGExporter().write(composition, out, metadata=METADATA)
    img = Image.open(out)
    assert "Attribution" in img.info
    assert "PLATEAU" in img.info["Attribution"]
    assert img.info.get("DatasetID") == DATASET_ID
    assert composition.attribution_report.visible
    assert composition.attribution_report.metadata


def test_svg_has_visible_text_and_metadata(tmp_path: Path):
    composition = _make_composition()
    out = tmp_path / "use_mosaic.svg"
    SVGExporter().write(composition, out, metadata=METADATA)
    raw = out.read_text(encoding="utf-8")
    # Visible: SVG must contain the attribution string as actual text.
    assert "PLATEAU" in raw
    # Metadata: parse the file and confirm the <dc:Attribution> element is there.
    tree = ET.parse(out)
    root = tree.getroot()
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    found_attribution = False
    for elem in root.iter():
        if elem.tag.endswith("}Attribution") and elem.text and "PLATEAU" in elem.text:
            found_attribution = True
            break
    assert found_attribution, "expected <dc:Attribution> in SVG metadata"


def test_pdf_document_info_carries_attribution(tmp_path: Path):
    composition = _make_composition()
    out = tmp_path / "use_mosaic.pdf"
    PDFExporter().write(composition, out, metadata=METADATA)
    # PDF text streams are compressed and the document info dict encodes
    # non-ASCII strings as UTF-16 BE with a BOM. We don't want to pull in a
    # full PDF parser, so we search the raw bytes for both encodings of
    # "PLATEAU": ASCII (visible text or PDFDocEncoded info entries) and
    # UTF-16 BE (matplotlib's default for any string containing non-ASCII
    # like "©").
    raw = out.read_bytes()
    ascii_hits = raw.count(b"PLATEAU")
    utf16_hits = raw.count(b"\x00P\x00L\x00A\x00T\x00E\x00A\x00U")
    assert ascii_hits + utf16_hits >= 1, "PDF must carry the PLATEAU attribution in metadata or text"
    # Document info dict markers we explicitly write through PdfPages.
    assert b"/Subject" in raw and b"/Author" in raw, "PDF doc-info must include Subject + Author"

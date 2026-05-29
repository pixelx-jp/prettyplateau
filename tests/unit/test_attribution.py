import datetime as _dt

import pytest

from prettyplateau.compose.attribution_injector import (
    AttributionInjectionReport,
    AttributionInjector,
    AttributionSpec,
)
from prettyplateau.core.errors import AttributionError


def test_attribution_requires_text():
    with pytest.raises(AttributionError):
        AttributionInjector(
            AttributionSpec(text="", dataset_id="x", generated_at=_dt.datetime.utcnow())
        )


def test_report_requires_both_visible_and_metadata():
    r = AttributionInjectionReport(visible=True, metadata=False)
    with pytest.raises(AttributionError):
        r.require_visible_and_metadata()
    r.metadata = True
    r.require_visible_and_metadata()


def test_primary_line_format():
    when = _dt.datetime(2026, 5, 28, tzinfo=_dt.timezone.utc)
    spec = AttributionSpec(
        text="© Project PLATEAU / MLIT (CC BY 4.0)",
        dataset_id="plateau-13113-shibuya-ku-2023-bldg",
        generated_at=when,
    )
    assert "Project PLATEAU" in spec.primary_line()
    assert "plateau-13113-shibuya-ku-2023-bldg" in spec.primary_line()
    assert "2026-05-28" in spec.primary_line()

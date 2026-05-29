"""Attribution-text extraction for `DataAccess`.

Plan layout splits attribution reading into its own module so callers can
import the read path independently of the larger `DataAccess` surface.
Implementation delegates to whatever adapter the caller's dataset came
from — the choice is recorded in `dataset.extras["backend"]`.
"""

from __future__ import annotations

from prettyplateau.data.access import CityDataset

# Default fallback when a dataset somehow has an empty attribution string —
# we'd rather emit the canonical CC BY 4.0 line than ship an artifact with
# no attribution at all. This should never trigger in practice because
# DataAccess sources attribution from `manifest.json`.
DEFAULT_ATTRIBUTION = "© Project PLATEAU / MLIT (CC BY 4.0)"


def get_attribution(dataset: CityDataset) -> str:
    return dataset.attribution or DEFAULT_ATTRIBUTION

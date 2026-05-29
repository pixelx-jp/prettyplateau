"""Top-level pytest configuration.

The `--update-baselines` option is consumed by the visual regression suite,
but it needs to be registered at the top level so pytest accepts it on the
command line regardless of which subdir you run.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="Refresh tests/visual/baselines/*.png from the current renderer output.",
    )

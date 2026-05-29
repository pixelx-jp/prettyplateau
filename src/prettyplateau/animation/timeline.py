"""Re-export TimelineSpec / TimelineFrame in the plan-shaped location.

Implementations live alongside the preset base class (so animation presets
return typed timelines without a circular import). The plan places them
under `animation/`, so this module re-exports them at the expected path.
"""

from __future__ import annotations

from prettyplateau.presets.base import TimelineFrame, TimelineSpec

__all__ = ["TimelineSpec", "TimelineFrame"]

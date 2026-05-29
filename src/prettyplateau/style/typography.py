"""Typography conventions used by the composer.

Centralised so font size choices stay consistent across title / subtitle /
legend / attribution. Sizes are in matplotlib points (1pt = 1/72 inch) so
they reflow correctly when DPI changes.
"""

from __future__ import annotations

TITLE_PT = 22
SUBTITLE_PT = 12
LEGEND_TITLE_PT = 10
LEGEND_ENTRY_PT = 9
ATTRIBUTION_PT = 7.5
CAPTION_PT = 7.5
ANNOTATION_PT = 9.0
# Plan: "attribution 字号不得低于可读阈值。默认不低于 6pt。"
MIN_ATTRIBUTION_PT = 6.0

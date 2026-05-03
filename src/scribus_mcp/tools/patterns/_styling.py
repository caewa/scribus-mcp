"""Shared styling constants used across pattern modules.

Centralising the magic numbers ("hairline = 0.3 pt", "thin axis = 0.4
pt", "default border = 0.6 pt") so they all read the same value and
contributors don't accidentally drift them.

Each pattern parameterises these where caller control matters; the
constants are the *defaults* the patterns reach for when no per-call
override is given.
"""

from __future__ import annotations

# Line widths in points, matching Scribus's line-width semantics.

# Hairline — the thinnest stroke we draw (gridlines, faint connectors,
# polygon-ring backgrounds). Designed to read as "barely there" at
# 100% PDF zoom on a 300 dpi print.
HAIRLINE_PT: float = 0.3

# Thin — used for radar rings, axis spokes, single-pixel-ish accents.
THIN_PT: float = 0.4

# Default border — used for chart outlines, callout-box borders, table
# rules. Visible at small print sizes but not heavy.
DEFAULT_BORDER_PT: float = 0.6


__all__ = ["HAIRLINE_PT", "THIN_PT", "DEFAULT_BORDER_PT"]

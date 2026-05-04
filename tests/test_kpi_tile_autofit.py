"""KPI value autofit must shrink the font when the rendered text would
overflow horizontally — not just vertically.

Regression: ``"Apache 2.0"`` at 22 pt in a ~33 mm-wide tile wrapped onto
two lines because the tile only auto-shrunk on vertical fit.
"""

from __future__ import annotations

import re

from scribus_mcp.tools.patterns.kpi_tile import render_kpi_tile_script


def _fragment(value: str, *, width_mm: float = 33.75, height_mm: float = 26.04) -> str:
    """Build the tile script fragment with default-ish KPI styling."""
    fragment, _font = render_kpi_tile_script(
        var_prefix="t",
        value=value,
        label="LICENSE",
        x_mm=0.0,
        y_mm=0.0,
        width_mm=width_mm,
        height_mm=height_mm,
    )
    return fragment


def _value_font_pt(fragment: str) -> float:
    """Extract the ``setFontSize(<pt>, _t_value)`` pt value from the fragment."""
    m = re.search(r"setFontSize\(([\d.]+), _t_value\)", fragment)
    assert m is not None, "no setFontSize call for _t_value found"
    return float(m.group(1))


def test_short_numeric_value_keeps_default_font():
    # ``"6"`` and ``"125"`` are the typical happy path: should not be
    # constrained by the new horizontal check (vertical autofit at
    # default tile height ≈ 26 mm caps at ~16.8 pt, the existing
    # behavior).
    assert _value_font_pt(_fragment("6")) >= 16.0
    assert _value_font_pt(_fragment("125")) >= 16.0


def test_apache_2_0_shrinks_to_fit_one_line():
    # Regression: at 22 pt the rendered width was ~70 pt (>24.75 mm
    # interior), so Scribus wrapped to two lines. With the horizontal
    # fit check the font drops to ~13 pt — which fits.
    fragment = _fragment("Apache 2.0")
    font_pt = _value_font_pt(fragment)
    # Conservative bound: the value should fit one line on the tile.
    # text_w = 33.75 - 9 = 24.75 mm = 70.16 pt; len = 10; 0.55 factor
    # ⇒ max ≈ 12.76 pt. Allow a small fudge for floor-rounding.
    assert font_pt < 14.0, f"expected horizontal autofit, got {font_pt} pt"


def test_long_label_value_shrinks_proportionally():
    fragment = _fragment("This is a very long value string that won't fit")
    font_pt = _value_font_pt(fragment)
    assert font_pt <= 6.5, f"expected aggressive shrink, got {font_pt} pt"


def test_minimum_floor_is_six_pt():
    # Pathologically long value: don't render at sub-readable size.
    fragment = _fragment("x" * 200)
    font_pt = _value_font_pt(fragment)
    assert font_pt >= 6.0


def test_wide_tile_keeps_default_font_for_apache_2_0():
    # Same value, generous tile width — horizontal check no longer
    # binds. Vertical autofit still caps at ~16.8 pt for default tile
    # height; that's the existing behavior we don't want to regress.
    fragment = _fragment("Apache 2.0", width_mm=80.0)
    assert _value_font_pt(fragment) >= 16.0

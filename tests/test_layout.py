"""Unit tests for :mod:`scribus_mcp.layout`.

Pure-Python tests — no Scribus, no bridge. Run with ``pytest tests/test_layout.py``.
"""

from __future__ import annotations

import pytest

from scribus_mcp.layout import PageCursor


def test_band_advances_y_by_height_plus_default_gap():
    pc = PageCursor(x_mm=10, y_mm=20, width_mm=100, default_gap_mm=4)
    s1 = pc.band(height_mm=14)
    assert s1["x_mm"] == 10
    assert s1["y_mm"] == 20
    assert s1["width_mm"] == 100
    assert s1["height_mm"] == 14
    # Cursor should now be at 20 + 14 + 4 = 38
    assert pc.y == 38

    s2 = pc.band(height_mm=10)
    assert s2["y_mm"] == 38
    assert pc.y == 52


def test_band_explicit_gap_overrides_default():
    pc = PageCursor(x_mm=0, y_mm=0, width_mm=50, default_gap_mm=4)
    pc.band(height_mm=10, gap_mm=2)
    assert pc.y == 12  # 10 + 2, not 10 + 4


def test_band_zero_gap_overrides_default():
    """gap_mm=0 must be distinguishable from "didn't pass gap_mm"."""
    pc = PageCursor(x_mm=0, y_mm=0, width_mm=50, default_gap_mm=4)
    pc.band(height_mm=10, gap_mm=0)
    assert pc.y == 10  # 10 + 0, not 10 + 4


def test_default_gap_mm_zero_when_unset():
    pc = PageCursor(x_mm=0, y_mm=0, width_mm=50)
    pc.band(height_mm=10)
    assert pc.y == 10


def test_slot_carries_center_coords():
    pc = PageCursor(x_mm=10, y_mm=0, width_mm=80)
    s = pc.band(height_mm=20)
    assert s["center_x"] == 10 + 80 / 2  # 50
    assert s["center_y"] == 0 + 20 / 2  # 10


def test_split_two_columns_share_y():
    pc = PageCursor(x_mm=10, y_mm=30, width_mm=100, default_gap_mm=4)
    left, right = pc.split([60, 40], height_mm=20)
    assert left["x_mm"] == 10
    assert left["width_mm"] == 60
    assert left["y_mm"] == 30
    assert right["x_mm"] == 70  # 10 + 60 (no inner gap)
    assert right["width_mm"] == 40
    assert right["y_mm"] == 30
    # Cursor advanced past the band + default gap
    assert pc.y == 30 + 20 + 4


def test_split_inner_gap_separates_columns():
    pc = PageCursor(x_mm=0, y_mm=0, width_mm=100)
    a, b, c = pc.split([30, 30, 30], inner_gap_mm=5, height_mm=10)
    assert a["x_mm"] == 0
    assert b["x_mm"] == 35  # 0 + 30 + 5
    assert c["x_mm"] == 70  # 0 + 30 + 5 + 30 + 5


def test_split_height_none_does_not_advance_cursor():
    pc = PageCursor(x_mm=0, y_mm=50, width_mm=100, default_gap_mm=4)
    slots = pc.split([50, 50])
    # No height_mm → slot heights are 0, cursor stays put
    assert slots[0]["height_mm"] == 0
    assert slots[1]["height_mm"] == 0
    assert pc.y == 50


def test_split_validates_total_width():
    pc = PageCursor(x_mm=0, y_mm=0, width_mm=100)
    with pytest.raises(ValueError, match="exceeds column width"):
        pc.split([60, 60], inner_gap_mm=0, height_mm=10)


def test_split_validates_with_inner_gap_too_large():
    pc = PageCursor(x_mm=0, y_mm=0, width_mm=100)
    # 40 + 40 + 30 (gap) = 110 > 100
    with pytest.raises(ValueError, match="exceeds column width"):
        pc.split([40, 40], inner_gap_mm=30, height_mm=10)


def test_split_explicit_gap_overrides_default():
    pc = PageCursor(x_mm=0, y_mm=0, width_mm=100, default_gap_mm=4)
    pc.split([50, 50], height_mm=20, gap_mm=10)
    assert pc.y == 30  # 20 + 10, not 20 + 4


def test_gap_advances_without_allocating():
    pc = PageCursor(x_mm=0, y_mm=10, width_mm=50)
    pc.gap(7)
    assert pc.y == 17


def test_jump_to_hard_sets_cursor():
    pc = PageCursor(x_mm=0, y_mm=10, width_mm=50)
    pc.band(height_mm=100)
    assert pc.y == 110
    pc.jump_to(20)
    assert pc.y == 20


def test_y_property_aliases_y_mm():
    pc = PageCursor(x_mm=0, y_mm=42, width_mm=50)
    assert pc.y == pc.y_mm == 42


def test_realistic_dashboard_layout():
    """End-to-end shape of a dashboard page — declares the sequence of
    bands the showcase actually uses, asserts the final cursor lands
    where we'd expect."""
    pc = PageCursor(x_mm=12, y_mm=38, width_mm=186, default_gap_mm=4)
    pc.band(height_mm=38)  # KPI row → cursor 80
    pc.split([85, 101], height_mm=45)  # bar + pie → cursor 129
    pc.split([80, 106], height_mm=56)  # radar + callout → cursor 189
    pc.band(height_mm=22)  # timeline → cursor 215
    pc.band(height_mm=32)  # comparison table → cursor 251
    assert pc.y == 251


def test_legacy_scripts_layout_shim_imports_same_class():
    """The scripts/_layout.py back-compat shim must re-export the same
    PageCursor (so old demo copies still work)."""
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        from _layout import PageCursor as Shim  # type: ignore[import-not-found]
    finally:
        sys.path.remove(str(scripts_dir))
    assert Shim is PageCursor

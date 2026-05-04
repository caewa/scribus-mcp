"""Unit tests for :mod:`scribus_mcp.tools.layouts._geometry`.

Pure-math, no Scribus required. Locks in the column / row / grid
splitter behaviour every layout pattern depends on.
"""

from __future__ import annotations

from scribus_mcp.tools.layouts._geometry import (
    compute_column_bboxes,
    compute_grid_bboxes,
    compute_row_bboxes,
)

# ----- compute_column_bboxes -----------------------------------------------


def test_columns_basic_split():
    bboxes = compute_column_bboxes(0, 0, 100, 50, 4, 0)
    assert len(bboxes) == 4
    for i, b in enumerate(bboxes):
        assert b["x_mm"] == 25 * i
        assert b["y_mm"] == 0
        assert b["width_mm"] == 25
        assert b["height_mm"] == 50


def test_columns_with_gap():
    # 100 wide, 3 columns, 5 mm gaps → (100 - 2*5)/3 = 30 each
    bboxes = compute_column_bboxes(10, 20, 100, 40, 3, 5)
    assert len(bboxes) == 3
    assert bboxes[0]["x_mm"] == 10
    assert bboxes[0]["width_mm"] == 30
    assert bboxes[1]["x_mm"] == 10 + 30 + 5  # 45
    assert bboxes[2]["x_mm"] == 10 + 2 * (30 + 5)  # 80
    # Right edge of the last column = 80 + 30 = 110 = x_mm + width_mm. Tight.


def test_columns_single_column_fills_width():
    bboxes = compute_column_bboxes(0, 0, 80, 20, 1, 99)  # gap_mm irrelevant for n=1
    assert len(bboxes) == 1
    assert bboxes[0]["width_mm"] == 80


def test_columns_zero_columns_returns_empty():
    assert compute_column_bboxes(0, 0, 100, 50, 0, 0) == []


def test_columns_negative_columns_returns_empty():
    assert compute_column_bboxes(0, 0, 100, 50, -1, 0) == []


def test_columns_gap_too_large_returns_empty():
    # 4 columns, 50 mm gaps → 3 gaps × 50 = 150 ≥ 100 width → infeasible
    assert compute_column_bboxes(0, 0, 100, 50, 4, 50) == []


def test_columns_preserves_height():
    bboxes = compute_column_bboxes(5, 7, 60, 33.5, 5, 1)
    for b in bboxes:
        assert b["y_mm"] == 7
        assert b["height_mm"] == 33.5


# ----- compute_row_bboxes --------------------------------------------------


def test_rows_basic_split():
    bboxes = compute_row_bboxes(0, 0, 100, 60, 3, 0)
    assert len(bboxes) == 3
    for i, b in enumerate(bboxes):
        assert b["x_mm"] == 0
        assert b["width_mm"] == 100
        assert b["y_mm"] == 20 * i
        assert b["height_mm"] == 20


def test_rows_with_gap():
    # 60 high, 3 rows, 4 mm gaps → (60 - 2*4)/3 = 17.333 each
    bboxes = compute_row_bboxes(0, 10, 50, 60, 3, 4)
    assert len(bboxes) == 3
    expected_h = (60 - 2 * 4) / 3
    assert abs(bboxes[0]["height_mm"] - expected_h) < 1e-9
    assert bboxes[0]["y_mm"] == 10
    assert abs(bboxes[1]["y_mm"] - (10 + expected_h + 4)) < 1e-9


def test_rows_zero_returns_empty():
    assert compute_row_bboxes(0, 0, 100, 50, 0, 0) == []


def test_rows_gap_too_large_returns_empty():
    assert compute_row_bboxes(0, 0, 50, 30, 4, 12) == []


# ----- compute_grid_bboxes -------------------------------------------------


def test_grid_basic_2x3():
    # 2 rows × 3 cols, no gaps. cell_w = 30, cell_h = 20.
    bboxes = compute_grid_bboxes(0, 0, 90, 40, 2, 3)
    assert len(bboxes) == 6
    # Row-major: r0c0, r0c1, r0c2, r1c0, r1c1, r1c2
    assert bboxes[0] == {"x_mm": 0, "y_mm": 0, "width_mm": 30, "height_mm": 20}
    assert bboxes[1] == {"x_mm": 30, "y_mm": 0, "width_mm": 30, "height_mm": 20}
    assert bboxes[2] == {"x_mm": 60, "y_mm": 0, "width_mm": 30, "height_mm": 20}
    assert bboxes[3] == {"x_mm": 0, "y_mm": 20, "width_mm": 30, "height_mm": 20}
    assert bboxes[5] == {"x_mm": 60, "y_mm": 20, "width_mm": 30, "height_mm": 20}


def test_grid_with_separate_gaps():
    bboxes = compute_grid_bboxes(0, 0, 100, 50, rows=2, cols=2,
                                 column_gap_mm=10, row_gap_mm=4)
    # cell_w = (100 - 1*10)/2 = 45; cell_h = (50 - 1*4)/2 = 23
    assert bboxes[0]["width_mm"] == 45
    assert bboxes[0]["height_mm"] == 23
    assert bboxes[1]["x_mm"] == 45 + 10  # 55
    assert bboxes[2]["y_mm"] == 23 + 4  # 27


def test_grid_zero_dimensions_return_empty():
    assert compute_grid_bboxes(0, 0, 100, 50, 0, 3) == []
    assert compute_grid_bboxes(0, 0, 100, 50, 3, 0) == []


def test_grid_gap_too_large_returns_empty():
    # 4 cols, 30 mm gaps → 3*30 = 90 ≥ 80 width
    assert compute_grid_bboxes(0, 0, 80, 50, 2, 4, column_gap_mm=30) == []
    # 5 rows, 12 mm gaps → 4*12 = 48 ≥ 40 height
    assert compute_grid_bboxes(0, 0, 80, 40, 5, 2, row_gap_mm=12) == []


def test_grid_single_cell():
    bboxes = compute_grid_bboxes(5, 7, 60, 30, 1, 1)
    assert len(bboxes) == 1
    assert bboxes[0] == {"x_mm": 5, "y_mm": 7, "width_mm": 60, "height_mm": 30}


def test_grid_fills_input_box_exactly():
    """The whole grid must exactly cover the input bbox — no slop."""
    rows, cols = 3, 4
    cgap, rgap = 6, 8
    x, y, w, h = 10, 20, 200, 120
    bboxes = compute_grid_bboxes(x, y, w, h, rows, cols, column_gap_mm=cgap, row_gap_mm=rgap)
    # Last cell's right edge should land exactly on x + w
    last = bboxes[-1]
    assert abs(last["x_mm"] + last["width_mm"] - (x + w)) < 1e-6
    assert abs(last["y_mm"] + last["height_mm"] - (y + h)) < 1e-6

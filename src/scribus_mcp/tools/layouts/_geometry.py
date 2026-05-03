"""Pure-math geometry helpers shared across layout tools.

Three primitives:
    compute_column_bboxes — N equal-width columns with horizontal gap
    compute_row_bboxes    — N equal-height rows with vertical gap
    compute_grid_bboxes   — 2D grid (rows × cols) with both gaps

All return a list of dicts with keys ``x_mm, y_mm, width_mm, height_mm``.
On invalid input (n <= 0, or available space < total gaps) they return
an empty list so callers can surface a clean error.
"""

from __future__ import annotations


def compute_column_bboxes(
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    columns: int,
    gap_mm: float,
) -> list[dict]:
    """Split a horizontal range into ``columns`` equal-width bboxes.

    Each bbox has the same height as the input. ``gap_mm`` between adjacent
    columns; can be 0 for no gap (table-style).
    """
    if columns < 1:
        return []
    if width_mm <= (columns - 1) * gap_mm:
        return []
    col_w = (width_mm - (columns - 1) * gap_mm) / columns
    return [
        {
            "x_mm": x_mm + i * (col_w + gap_mm),
            "y_mm": y_mm,
            "width_mm": col_w,
            "height_mm": height_mm,
        }
        for i in range(columns)
    ]


def compute_row_bboxes(
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    rows: int,
    gap_mm: float,
) -> list[dict]:
    """Split a vertical range into ``rows`` equal-height bboxes.

    Mirror of compute_column_bboxes for the vertical axis.
    """
    if rows < 1:
        return []
    if height_mm <= (rows - 1) * gap_mm:
        return []
    row_h = (height_mm - (rows - 1) * gap_mm) / rows
    return [
        {
            "x_mm": x_mm,
            "y_mm": y_mm + i * (row_h + gap_mm),
            "width_mm": width_mm,
            "height_mm": row_h,
        }
        for i in range(rows)
    ]


def compute_grid_bboxes(
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    rows: int,
    cols: int,
    column_gap_mm: float = 0.0,
    row_gap_mm: float = 0.0,
) -> list[dict]:
    """2D grid: ``rows × cols`` bboxes, with separate column (horizontal)
    and row (vertical) gaps. Returns row-major:
    ``[r0c0, r0c1, …, r1c0, r1c1, …]``.

    Each bbox has the same dimensions, computed so the whole grid exactly
    fills the input bbox.
    """
    if rows < 1 or cols < 1:
        return []
    if width_mm <= (cols - 1) * column_gap_mm:
        return []
    if height_mm <= (rows - 1) * row_gap_mm:
        return []
    cell_w = (width_mm - (cols - 1) * column_gap_mm) / cols
    cell_h = (height_mm - (rows - 1) * row_gap_mm) / rows
    out: list[dict] = []
    for r in range(rows):
        for c in range(cols):
            out.append(
                {
                    "x_mm": x_mm + c * (cell_w + column_gap_mm),
                    "y_mm": y_mm + r * (cell_h + row_gap_mm),
                    "width_mm": cell_w,
                    "height_mm": cell_h,
                }
            )
    return out

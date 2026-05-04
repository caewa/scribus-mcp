"""Headers + rows + optional zebra shading + horizontal rule.

Single-script-body design: every header cell, zebra background, body
cell, and the divider line is computed Python-side and emitted as one
``backend.script()`` call.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes
from scribus_mcp.tools.patterns._styling import THIN_PT


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_comparison_table(
        headers: list[str],
        rows: list[list[str]],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        column_widths: list[float] | None = None,
        row_height_mm: float = 7.0,
        header_height_mm: float = 6.5,
        header_color: str = "Black",
        header_font_size_pt: float = 8.0,
        cell_color: str = "Black",
        cell_font_size_pt: float = 9.0,
        zebra: bool = True,
        zebra_fill_color: str = "Black",
        zebra_fill_shade: int = 6,
        rule_color: str = "Black",
        rule_shade: int = 25,
        mode: Mode = "auto",
    ) -> dict:
        """Render a flat comparison table from headers + rows of cell text.

        If ``column_widths`` is omitted, the width is split evenly across
        columns. ``zebra`` shades alternating rows lightly. A horizontal
        rule is drawn under the header.
        """
        if not headers:
            return {"ok": False, "error": "headers can't be empty"}
        ncols = len(headers)
        for i, row in enumerate(rows):
            if len(row) != ncols:
                return {
                    "ok": False,
                    "error": f"row {i} has {len(row)} cells, expected {ncols}",
                }
        if column_widths is None:
            equal = compute_column_bboxes(0, 0, width_mm, 1, ncols, 0)
            column_widths = [b["width_mm"] for b in equal]
        elif len(column_widths) != ncols:
            return {"ok": False, "error": f"column_widths must have {ncols} entries"}

        # ---- Pre-compute every primitive's spec Python-side -------------

        # Headers: list of (x, y, w, h, text)
        headers_spec = []
        col_x = x_mm
        for i, h in enumerate(headers):
            headers_spec.append(
                (col_x, y_mm, column_widths[i], float(header_height_mm), clean_user_text(str(h)))
            )
            col_x += column_widths[i]

        rule_y = y_mm + header_height_mm + 0.5

        # Zebra backgrounds: list of (x, y, w, h)
        zebra_spec = []
        # Cells: list of rows, each row is list of (x, y, w, h, text)
        cells_spec: list[list[tuple]] = []
        row_y = rule_y + 1.5
        for r_idx, row in enumerate(rows):
            if zebra and r_idx % 2 == 1:
                zebra_spec.append((x_mm, row_y - 0.5, width_mm, float(row_height_mm)))
            row_cells_spec = []
            col_x = x_mm
            for i, cell_text in enumerate(row):
                row_cells_spec.append(
                    (
                        col_x,
                        row_y,
                        column_widths[i],
                        float(row_height_mm - 1),
                        clean_user_text(str(cell_text)),
                    )
                )
                col_x += column_widths[i]
            cells_spec.append(row_cells_spec)
            row_y += row_height_mm

        # Flatten cells_spec → flat list with row_idx so script can rebuild groups.
        cells_flat = [
            (r_idx, c[0], c[1], c[2], c[3], c[4])
            for r_idx, row in enumerate(cells_spec)
            for c in row
        ]

        body = f"""
import scribus as _s

_header_names = []
for _x, _y, _w, _h, _text in {headers_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(header_font_size_pt)}, _n)
    _s.setTextColor({header_color!r}, _n)
    _header_names.append(_n)

_rule = _s.createLine({x_mm}, {rule_y}, {x_mm + width_mm}, {rule_y})
_s.setLineColor({rule_color!r}, _rule)
_s.setLineShade({int(rule_shade)}, _rule)
_s.setLineWidth({THIN_PT}, _rule)

_zebra_names = []
for _x, _y, _w, _h in {zebra_spec!r}:
    _n = _s.createRect(_x, _y, _w, _h)
    _s.setFillColor({zebra_fill_color!r}, _n)
    _s.setFillShade({int(zebra_fill_shade)}, _n)
    _s.setLineColor("None", _n)
    _zebra_names.append(_n)

_cell_rows = [[] for _ in range({len(cells_spec)})]
for _r_idx, _x, _y, _w, _h, _text in {cells_flat!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(cell_font_size_pt)}, _n)
    _s.setTextColor({cell_color!r}, _n)
    _cell_rows[_r_idx].append(_n)

_value = {{
    "headers": _header_names,
    "rule": _rule,
    "zebra": _zebra_names,
    "cells": _cell_rows,
}}
"""

        backend = await get_backend(ctx, mode)
        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "comparison_table script failed"}

        out = res.value or {}
        return {
            "ok": True,
            "headers": out.get("headers", []),
            "cells": out.get("cells", []),
            "zebra_rows": out.get("zebra", []),
            "rows_drawn": len(rows),
            "error": None,
        }

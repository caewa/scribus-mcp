"""Two-column body text — left + right text frames inside a bounding box."""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_two_column_text(
        text_left: str,
        text_right: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        gap_mm: float = 6.0,
        font_size_pt: float = 10.0,
        text_color: str = "Black",
        alignment: str = "justify",
        line_spacing_pt: float = 13.0,
        mode: Mode = "auto",
    ) -> dict:
        """Two text columns side by side inside (x, y, width, height).

        ``alignment`` is applied to both columns (``left|center|right|justify|forced``).
        Returns the names of both frames so callers can re-style afterwards.
        """
        align_map = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}
        if alignment not in align_map:
            return {"ok": False, "error": f"alignment must be one of {sorted(align_map)}"}

        # Generic column math — N=2 case of the shared helper.
        bboxes = compute_column_bboxes(x_mm, y_mm, width_mm, height_mm, 2, gap_mm)
        if not bboxes:
            return {"ok": False, "error": "width_mm must be greater than gap_mm"}
        left_bb, right_bb = bboxes

        backend = await get_backend(ctx, mode)

        # Left column
        lr = await backend.call(
            "createText",
            left_bb["x_mm"],
            left_bb["y_mm"],
            left_bb["width_mm"],
            left_bb["height_mm"],
        )
        if not lr.ok:
            return {"ok": False, "error": f"left column failed: {lr.error}"}
        ln = lr.value
        await backend.call("setText", text_left, ln)
        await backend.call("setFontSize", float(font_size_pt), ln)
        await backend.call("setTextColor", text_color, ln)
        await backend.call("setTextAlignment", align_map[alignment], ln)
        await backend.call("setLineSpacing", float(line_spacing_pt), ln)

        # Right column
        rr = await backend.call(
            "createText",
            right_bb["x_mm"],
            right_bb["y_mm"],
            right_bb["width_mm"],
            right_bb["height_mm"],
        )
        if not rr.ok:
            return {"ok": False, "error": f"right column failed: {rr.error}", "left": ln}
        rn = rr.value
        await backend.call("setText", text_right, rn)
        await backend.call("setFontSize", float(font_size_pt), rn)
        await backend.call("setTextColor", text_color, rn)
        await backend.call("setTextAlignment", align_map[alignment], rn)
        await backend.call("setLineSpacing", float(line_spacing_pt), rn)

        return {
            "ok": True,
            "left": ln,
            "right": rn,
            "column_width_mm": left_bb["width_mm"],
            "error": None,
        }

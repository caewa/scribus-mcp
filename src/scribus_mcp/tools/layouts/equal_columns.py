"""Split a bounding box into N equal columns with gaps.

The generic primitive — any row-style layout (KPI row, card row, image
strip, etc.) builds on this. Returns frame names + their bboxes so the
caller can either fill them directly or compose other tools on top.

The math itself lives in ``_geometry.py``. Other modules import
``compute_column_bboxes`` from there directly.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_equal_columns(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        columns: int,
        gap_mm: float = 3.0,
        frame_type: str = "text",
        fill_color: str = "None",
        fill_shade: int = 100,
        mode: Mode = "auto",
    ) -> dict:
        """Split a bounding box into ``columns`` equal-width frames with
        ``gap_mm`` between them. Returns the names + bboxes of every frame
        so the caller can fill / style each independently.

        ``frame_type`` ∈ {``text``, ``rectangle``, ``image``} — controls what
        kind of frame is created. Use ``text`` for body content, ``rectangle``
        for background panels, ``image`` for picture frames.

        Per-tile width is ``(width_mm - (columns - 1) * gap_mm) / columns``,
        which never overflows the bounding box. This is the generic primitive
        for any row-style layout (``create_kpi_row`` builds on it).
        """
        if columns < 1:
            return {"ok": False, "error": "columns must be >= 1"}
        if width_mm <= (columns - 1) * gap_mm:
            return {
                "ok": False,
                "error": f"width_mm ({width_mm}) too small for {columns} columns + gap {gap_mm}",
            }
        if frame_type not in ("text", "rectangle", "image"):
            return {"ok": False, "error": "frame_type must be one of: text, rectangle, image"}

        bboxes = compute_column_bboxes(x_mm, y_mm, width_mm, height_mm, columns, gap_mm)
        if not bboxes:
            return {"ok": False, "error": "could not compute bboxes"}

        backend = await get_backend(ctx, mode)
        create_method = {
            "text": "createText",
            "rectangle": "createRect",
            "image": "createImage",
        }[frame_type]

        frames: list[dict] = []
        for i, b in enumerate(bboxes):
            r = await backend.call(
                create_method, b["x_mm"], b["y_mm"], b["width_mm"], b["height_mm"]
            )
            if not r.ok:
                return {"ok": False, "error": f"column {i} failed: {r.error}", "frames": frames}
            name = r.value
            if frame_type == "rectangle" and fill_color != "None":
                await backend.call("setFillColor", fill_color, name)
                await backend.call("setFillShade", int(fill_shade), name)
                await backend.call("setLineColor", "None", name)
            frames.append({"name": name, **b})

        return {
            "ok": True,
            "frames": frames,
            "columns": columns,
            "column_width_mm": bboxes[0]["width_mm"],
            "error": None,
        }

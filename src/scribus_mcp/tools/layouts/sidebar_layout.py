"""Sidebar layout — narrow side column + wide main column."""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.palette import resolve_color


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_sidebar_layout(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        sidebar_side: str = "left",
        sidebar_width_mm: float = 50.0,
        gap_mm: float = 6.0,
        sidebar_fill_color: str = "surface",
        sidebar_fill_shade: int | None = None,
        sidebar_padding_mm: float = 4.0,
        sidebar_text: str = "",
        sidebar_color: str = "ink",
        sidebar_font_size_pt: float = 9.0,
        sidebar_alignment: str = "left",
        sidebar_line_spacing_pt: float = 12.0,
        main_text: str = "",
        main_color: str = "ink",
        main_font_size_pt: float = 10.0,
        main_alignment: str = "justify",
        main_line_spacing_pt: float = 13.0,
        mode: Mode = "auto",
    ) -> dict:
        """Two-column layout where one column is a narrow sidebar (shaded
        background, typically holds notes / pull-quotes / metadata) and the
        other is the main body.

        ``sidebar_side`` ∈ {"left", "right"}.

        Both ``sidebar_text`` and ``main_text`` are optional — pass empty
        strings to leave the frames ready for the caller to fill (e.g. with
        ``import_markdown`` for the main column).
        """
        if sidebar_side not in ("left", "right"):
            return {"ok": False, "error": "sidebar_side must be 'left' or 'right'"}
        if sidebar_width_mm + gap_mm >= width_mm:
            return {"ok": False, "error": "sidebar_width_mm + gap_mm must be < width_mm"}
        align_map = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}
        if sidebar_alignment not in align_map:
            return {"ok": False, "error": f"sidebar_alignment must be one of {sorted(align_map)}"}
        if main_alignment not in align_map:
            return {"ok": False, "error": f"main_alignment must be one of {sorted(align_map)}"}

        backend = await get_backend(ctx, mode)
        sidebar_fill_color, sidebar_fill_shade = await resolve_color(
            backend, sidebar_fill_color, fallback_shade=8, current_shade=sidebar_fill_shade,
        )
        sidebar_color, _ = await resolve_color(backend, sidebar_color)
        main_color, _ = await resolve_color(backend, main_color)
        main_w = width_mm - sidebar_width_mm - gap_mm

        if sidebar_side == "left":
            sb_x = x_mm
            main_x = x_mm + sidebar_width_mm + gap_mm
        else:
            main_x = x_mm
            sb_x = x_mm + main_w + gap_mm

        # Sidebar background (shaded panel)
        bgr = await backend.call("createRect", sb_x, y_mm, sidebar_width_mm, height_mm)
        if not bgr.ok:
            return {"ok": False, "error": f"sidebar background failed: {bgr.error}"}
        bg_name = bgr.value
        await backend.call("setFillColor", sidebar_fill_color, bg_name)
        await backend.call("setFillShade", int(sidebar_fill_shade), bg_name)
        await backend.call("setLineColor", "None", bg_name)

        # Sidebar text frame inset by padding
        sr = await backend.call(
            "createText",
            sb_x + sidebar_padding_mm,
            y_mm + sidebar_padding_mm,
            sidebar_width_mm - 2 * sidebar_padding_mm,
            height_mm - 2 * sidebar_padding_mm,
        )
        if not sr.ok:
            return {"ok": False, "error": f"sidebar text failed: {sr.error}", "sidebar_bg": bg_name}
        sn = sr.value
        if sidebar_text:
            await backend.call("setText", sidebar_text, sn)
        await backend.call("setFontSize", float(sidebar_font_size_pt), sn)
        await backend.call("setTextColor", sidebar_color, sn)
        await backend.call("setTextAlignment", align_map[sidebar_alignment], sn)
        await backend.call("setLineSpacing", float(sidebar_line_spacing_pt), sn)

        # Main column text frame (no background — caller can add one if wanted)
        mr = await backend.call("createText", main_x, y_mm, main_w, height_mm)
        if not mr.ok:
            return {
                "ok": False,
                "error": f"main text failed: {mr.error}",
                "sidebar_bg": bg_name,
                "sidebar_text": sn,
            }
        mn = mr.value
        if main_text:
            await backend.call("setText", main_text, mn)
        await backend.call("setFontSize", float(main_font_size_pt), mn)
        await backend.call("setTextColor", main_color, mn)
        await backend.call("setTextAlignment", align_map[main_alignment], mn)
        await backend.call("setLineSpacing", float(main_line_spacing_pt), mn)

        return {
            "ok": True,
            "sidebar_bg": bg_name,
            "sidebar_text": sn,
            "main_text": mn,
            "sidebar_width_mm": sidebar_width_mm,
            "main_width_mm": main_w,
            "error": None,
        }

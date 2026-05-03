"""Bordered, lightly-shaded box with a title and a body paragraph.

Single-script-body design.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_callout_box(
        title: str,
        body: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        fill_color: str = "Black",
        fill_shade: int = 8,
        border_color: str = "Black",
        border_shade: int = 25,
        border_width_pt: float = 0.6,
        title_color: str = "Black",
        title_font_size_pt: float = 11,
        body_color: str = "Black",
        body_font_size_pt: float = 9,
        padding_mm: float = 4.0,
        title_height_mm: float = 6.0,
        mode: Mode = "auto",
    ) -> dict:
        """A bordered, lightly-shaded box with a title and a body paragraph.
        Useful for tips, warnings, callouts, sidebars."""
        body_y = y_mm + padding_mm + title_height_mm + 1
        body_h = height_mm - (padding_mm * 2) - title_height_mm - 1
        text_w = width_mm - 2 * padding_mm

        script = f"""
import scribus as _s

_bg = _s.createRect({x_mm}, {y_mm}, {width_mm}, {height_mm})
_s.setFillColor({fill_color!r}, _bg)
_s.setFillShade({int(fill_shade)}, _bg)
_s.setLineColor({border_color!r}, _bg)
_s.setLineShade({int(border_shade)}, _bg)
_s.setLineWidth({float(border_width_pt)}, _bg)

_title = _s.createText({x_mm + padding_mm}, {y_mm + padding_mm}, {text_w}, {title_height_mm})
_s.setText({title!r}, _title)
_s.setFontSize({float(title_font_size_pt)}, _title)
_s.setTextColor({title_color!r}, _title)

_body = _s.createText({x_mm + padding_mm}, {body_y}, {text_w}, {body_h})
_s.setText({body!r}, _body)
_s.setFontSize({float(body_font_size_pt)}, _body)
_s.setTextColor({body_color!r}, _body)
_s.setTextAlignment(3, _body)  # justify

_value = {{"background": _bg, "title": _title, "body": _body}}
"""

        backend = await get_backend(ctx, mode)
        res = await backend.script(script, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "callout_box script failed"}
        out = res.value or {}
        return {
            "ok": True,
            "background": out.get("background"),
            "title": out.get("title"),
            "body": out.get("body"),
            "error": None,
        }

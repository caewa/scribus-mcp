"""Bordered, lightly-shaded box with a title and a body paragraph.

Single-script-body design.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools._fit import FIT_TEXT_FRAME_HELPER
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_callout_box(
        title: str,
        body: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        fill_color: str = "surface",
        fill_shade: int | None = None,
        border_color: str = "muted",
        border_shade: int | None = None,
        border_width_pt: float = 0.6,
        title_color: str = "ink",
        title_font_size_pt: float = 11,
        body_color: str = "ink",
        body_font_size_pt: float = 9,
        padding_mm: float = 4.0,
        title_height_mm: float = 6.0,
        auto_height: bool = True,
        mode: Mode = "auto",
    ) -> dict:
        """A bordered, lightly-shaded box with a title and a body paragraph.
        Useful for tips, warnings, callouts, sidebars.

        ``auto_height`` (default ``True``) measures the rendered body
        text and resizes the body frame + the background rect so the
        box fits snugly around its content. The returned ``height_mm``
        field carries the final box height (which can be used by
        ``PageCursor.jump_to`` to chain). Pass ``auto_height=False``
        only when you specifically need the box pinned to the
        caller-provided ``height_mm``.

        Color slots default to palette roles — ``surface`` (fill),
        ``muted`` (border), ``ink`` (title + body). Define those names
        with ``define_color_rgb`` and the box adopts them automatically;
        leave the palette unset and slots fall back to the historical
        ``Black`` / shaded defaults.
        """
        body_y = y_mm + padding_mm + title_height_mm + 1
        body_h = height_mm - (padding_mm * 2) - title_height_mm - 1
        text_w = width_mm - 2 * padding_mm
        title = clean_user_text(title)
        body = clean_user_text(body)
        backend = await get_backend(ctx, mode)
        fill_color, fill_shade = await resolve_color(
            backend, fill_color, fallback_shade=8, current_shade=fill_shade,
        )
        border_color, border_shade = await resolve_color(
            backend, border_color, fallback_shade=25, current_shade=border_shade,
        )
        title_color, _ = await resolve_color(backend, title_color)
        body_color, _ = await resolve_color(backend, body_color)

        autofit_block = ""
        if auto_height:
            # After setText, fit the body frame to its rendered height
            # and resize the background rect so its bottom edge sits
            # ``padding_mm`` below the body's new bottom.
            autofit_block = f"""
{FIT_TEXT_FRAME_HELPER}

_fit_h = _fit_text_frame(_body, {text_w}, {body_h})
# Final box height = top padding + title strip + 1mm gap + body + bottom padding.
_box_h = {padding_mm} + {title_height_mm} + 1 + _fit_h + {padding_mm}
_s.sizeObject({width_mm}, _box_h, _bg)
"""

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
{autofit_block}
# Report the final box height — same as ``height_mm`` when not auto-fitting.
try:
    _final_h = _box_h
except NameError:
    _final_h = {height_mm}

_value = {{"background": _bg, "title": _title, "body": _body, "height_mm": _final_h}}
"""

        res = await backend.script(script, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "callout_box script failed"}
        out = res.value or {}
        group_name = await group_created_objects(
            backend,
            [out.get("background"), out.get("title"), out.get("body")],
        )
        return {
            "ok": True,
            "background": out.get("background"),
            "title": out.get("title"),
            "body": out.get("body"),
            "group": group_name,
            "height_mm": out.get("height_mm"),
            "error": None,
        }

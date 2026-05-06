"""Eyebrow + big title + optional accent rule — reusable section divider."""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_section_header(
        title: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        eyebrow: str = "",
        title_color: str = "ink",
        title_font_size_pt: float = 16.0,
        title_height_mm: float = 7.0,
        eyebrow_color: str = "accent",
        eyebrow_font_size_pt: float = 7.0,
        eyebrow_height_mm: float = 4.0,
        with_rule: bool = True,
        rule_color: str = "muted",
        rule_shade: int | None = None,
        rule_width_pt: float = 0.6,
        rule_offset_mm: float = 0.5,
        mode: Mode = "auto",
    ) -> dict:
        """A consistent section header: small uppercase eyebrow, bold title,
        and an optional thin accent rule below.

        Use to break long documents into navigable sections without inventing
        a new visual hierarchy each time.

        Color slots default to palette roles — ``ink`` (title),
        ``accent`` (eyebrow), ``muted`` (rule). Define those names with
        ``define_color_rgb`` and every header inherits them; leave the
        palette unset and slots fall back to ``Black`` at the historical
        shades.
        """
        backend = await get_backend(ctx, mode)
        title_color, _ = await resolve_color(backend, title_color)
        eyebrow_color, _ = await resolve_color(backend, eyebrow_color)
        rule_color, rule_shade = await resolve_color(
            backend, rule_color, fallback_shade=30, current_shade=rule_shade,
        )
        title = clean_user_text(title)
        eyebrow = clean_user_text(eyebrow)
        eyebrow_name: str | None = None
        rule_name: str | None = None
        cur_y = y_mm

        # Eyebrow (optional)
        if eyebrow:
            er = await backend.call("createText", x_mm, cur_y, width_mm, eyebrow_height_mm)
            if not er.ok:
                return {"ok": False, "error": f"eyebrow failed: {er.error}"}
            eyebrow_name = er.value
            await backend.call("setText", eyebrow.upper(), eyebrow_name)
            await backend.call("setFontSize", float(eyebrow_font_size_pt), eyebrow_name)
            await backend.call("setTextColor", eyebrow_color, eyebrow_name)
            cur_y += eyebrow_height_mm + 0.5

        # Title
        tr = await backend.call("createText", x_mm, cur_y, width_mm, title_height_mm)
        if not tr.ok:
            return {"ok": False, "error": f"title failed: {tr.error}"}
        title_name = tr.value
        await backend.call("setText", title, title_name)
        await backend.call("setFontSize", float(title_font_size_pt), title_name)
        await backend.call("setTextColor", title_color, title_name)
        cur_y += title_height_mm + rule_offset_mm

        # Optional accent rule
        if with_rule:
            rr = await backend.call("createLine", x_mm, cur_y, x_mm + width_mm, cur_y)
            if rr.ok:
                rule_name = rr.value
                await backend.call("setLineColor", rule_color, rule_name)
                await backend.call("setLineShade", int(rule_shade), rule_name)
                await backend.call("setLineWidth", float(rule_width_pt), rule_name)

        group_name = await group_created_objects(
            backend, [eyebrow_name, title_name, rule_name]
        )
        return {
            "ok": True,
            "eyebrow": eyebrow_name,
            "title": title_name,
            "rule": rule_name,
            "group": group_name,
            "bottom_y_mm": cur_y + (0.5 if with_rule else 0),
            "error": None,
        }

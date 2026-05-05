"""Vertical list of numbered steps — circle badges + title + body.

Composes the dot_label and callout_box patterns into a typical "Getting
Started" / "How it works" idiom. One tool call replaces the dozens of
primitive calls a hand-rolled step list takes.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.layouts._geometry import compute_row_bboxes
from scribus_mcp.tools.palette import resolve_color


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_numbered_steps(
        items: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        item_height_mm: float = 32.0,
        gap_mm: float = 6.0,
        badge_diameter_mm: float = 12.0,
        badge_fill_color: str = "accent",
        badge_text_color: str = "White",
        badge_text_font_size_pt: float = 14.0,
        body_fill_color: str = "surface",
        body_fill_shade: int | None = None,
        body_border_color: str = "muted",
        body_border_shade: int | None = None,
        body_border_width_pt: float = 0.5,
        title_color: str = "ink",
        title_font_size_pt: float = 11.0,
        body_text_color: str = "ink",
        body_text_font_size_pt: float = 9.0,
        body_padding_mm: float = 4.0,
        body_title_height_mm: float = 6.0,
        body_x_offset_mm: float = 6.0,
        mode: Mode = "auto",
    ) -> dict:
        """Vertical list of numbered steps. Each item is a dict with:
            ``title``: short headline
            ``body`` : longer description

        Layout per step: a numbered circle on the left + a callout-style
        rectangle on the right with title + body. The badge digit is
        pixel-perfectly centered (text is converted to outline polygons
        and its bbox measured for exact placement).
        """
        if not items:
            return {"ok": False, "error": "items must not be empty"}
        for i, it in enumerate(items):
            if "title" not in it or "body" not in it:
                return {"ok": False, "error": f"item {i} needs 'title' and 'body'"}

        backend = await get_backend(ctx, mode)
        badge_fill_color, _ = await resolve_color(backend, badge_fill_color)
        badge_text_color, _ = await resolve_color(backend, badge_text_color, fallback_color="White")
        body_fill_color, body_fill_shade = await resolve_color(
            backend, body_fill_color, fallback_shade=8, current_shade=body_fill_shade,
        )
        body_border_color, body_border_shade = await resolve_color(
            backend, body_border_color, fallback_shade=25, current_shade=body_border_shade,
        )
        title_color, _ = await resolve_color(backend, title_color)
        body_text_color, _ = await resolve_color(backend, body_text_color)
        out: list[dict] = []
        body_x = x_mm + badge_diameter_mm + body_x_offset_mm
        body_w = width_mm - badge_diameter_mm - body_x_offset_mm

        # Row bboxes — shared row math (vertical equivalent of compute_column_bboxes).
        # Total height = N * item_height + (N-1) * gap.
        n = len(items)
        total_h = n * item_height_mm + max(0, n - 1) * gap_mm
        rows = compute_row_bboxes(x_mm, y_mm, width_mm, total_h, n, gap_mm)

        for i, it in enumerate(items):
            top = rows[i]["y_mm"]
            cy = top + item_height_mm / 2  # vertical center of the row
            cx = x_mm + badge_diameter_mm / 2

            # Badge — circle + outlined-text digit, pixel-centered.
            cir = await backend.call(
                "createEllipse",
                cx - badge_diameter_mm / 2,
                cy - badge_diameter_mm / 2,
                badge_diameter_mm,
                badge_diameter_mm,
            )
            if not cir.ok:
                return {"ok": False, "error": f"step {i}: badge circle failed: {cir.error}"}
            circle_name = cir.value
            await backend.call("setFillColor", badge_fill_color, circle_name)
            await backend.call("setLineColor", "None", circle_name)

            # Text → outline → measure → reposition. traceText deletes the
            # original frame and creates one polygon per glyph; for multi-digit
            # numbers we group them so we have a single bbox to recenter.
            badge_body = (
                "import scribus as _s\n"
                f"_play = {float(badge_diameter_mm) * 2.5}\n"
                "_before = set(_it[0] for _it in (_s.getPageItems() or []))\n"
                f"_t = _s.createText({cx} - _play / 2, {cy} - _play / 2, _play, _play)\n"
                f"_s.setText({str(i + 1)!r}, _t)\n"
                f"_s.setFontSize({float(badge_text_font_size_pt)}, _t)\n"
                f"_s.setTextColor({badge_text_color!r}, _t)\n"
                "_s.setTextAlignment(1, _t)\n"
                "_s.setTextVerticalAlignment(1, _t)\n"
                "_s.layoutText(_t)\n"
                "_s.traceText(_t)\n"
                "_after = set(_it[0] for _it in (_s.getPageItems() or []))\n"
                "_new = sorted(_after - _before)\n"
                "if len(_new) == 1:\n"
                "    _final = _new[0]\n"
                "elif len(_new) > 1:\n"
                "    _s.groupObjects(_new)\n"
                "    _post = set(_it[0] for _it in (_s.getPageItems() or []))\n"
                "    _grouped = sorted(_post - _before - set(_new))\n"
                "    _final = _grouped[-1] if _grouped else _new[0]\n"
                "else:\n"
                "    raise RuntimeError('traceText produced no polygons')\n"
                "_w, _h = _s.getSize(_final)\n"
                f"_s.moveObjectAbs({cx} - _w / 2, {cy} - _h / 2, _final)\n"
                "_value = _final"
            )
            badge_text_res = await backend.script(badge_body, result_expr="_value")
            digit_name = badge_text_res.value if badge_text_res.ok else None
            digit_error = None if badge_text_res.ok else (badge_text_res.error or "badge digit failed")

            # Body container — bordered shaded rectangle (callout-style)
            box = await backend.call("createRect", body_x, top, body_w, item_height_mm)
            if not box.ok:
                return {"ok": False, "error": f"step {i}: body box failed: {box.error}"}
            box_name = box.value
            await backend.call("setFillColor", body_fill_color, box_name)
            await backend.call("setFillShade", int(body_fill_shade), box_name)
            await backend.call("setLineColor", body_border_color, box_name)
            await backend.call("setLineShade", int(body_border_shade), box_name)
            await backend.call("setLineWidth", float(body_border_width_pt), box_name)

            # Title
            tr = await backend.call(
                "createText",
                body_x + body_padding_mm,
                top + body_padding_mm,
                body_w - 2 * body_padding_mm,
                body_title_height_mm,
            )
            title_name = None
            if tr.ok:
                title_name = tr.value
                await backend.call("setText", clean_user_text(str(it["title"])), title_name)
                await backend.call("setFontSize", float(title_font_size_pt), title_name)
                await backend.call("setTextColor", title_color, title_name)

            # Body text
            body_y = top + body_padding_mm + body_title_height_mm + 1
            body_h = item_height_mm - 2 * body_padding_mm - body_title_height_mm - 1
            br = await backend.call(
                "createText",
                body_x + body_padding_mm,
                body_y,
                body_w - 2 * body_padding_mm,
                body_h,
            )
            body_name = None
            if br.ok:
                body_name = br.value
                await backend.call("setText", clean_user_text(str(it["body"])), body_name)
                await backend.call("setFontSize", float(body_text_font_size_pt), body_name)
                await backend.call("setTextColor", body_text_color, body_name)

            step_record = {
                "circle": circle_name,
                "digit": digit_name,
                "container": box_name,
                "title": title_name,
                "body": body_name,
            }
            if digit_error:
                step_record["digit_error"] = digit_error
            out.append(step_record)

        # Surface aggregate `digit_warnings` count so callers don't have
        # to scan every step record to know whether any badge digits
        # failed to outline.
        digit_warnings = sum(1 for s in out if s.get("digit_error"))
        return {
            "ok": True,
            "steps": out,
            "count": len(out),
            "digit_warnings": digit_warnings,
            "error": None,
        }

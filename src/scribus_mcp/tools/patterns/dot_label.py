"""Filled circle with centered text inside — step badges, status dots, etc.

``create_dot_label`` is the general primitive: any text. ``create_numbered_badge``
is a thin wrapper that takes an integer and styles defaults for a step-marker
look (the kind seen in numbered "Getting Started" lists).
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_dot_label(
        text: str,
        center_x_mm: float,
        center_y_mm: float,
        diameter_mm: float = 12.0,
        fill_color: str = "accent",
        fill_shade: int | None = None,
        line_color: str = "None",
        line_width_pt: float = 0.0,
        text_color: str = "White",
        text_font_size_pt: float = 14.0,
        mode: Mode = "auto",
    ) -> dict:
        """Filled circle with centered text inside it.

        Common use cases: step markers in numbered lists, status dots
        ("✓", "!", letters, numbers), small icon-like badges next to titles.

        ``center_x_mm``/``center_y_mm`` is the dot's geometric center
        (which is also where the text is centered). ``diameter_mm`` controls
        both the dot size and the text frame.

        Returns the names of the circle and the text frame so callers can
        re-style afterwards.
        """
        if diameter_mm <= 0:
            return {"ok": False, "error": "diameter_mm must be > 0"}

        radius = diameter_mm / 2.0
        rect_x = center_x_mm - radius
        rect_y = center_y_mm - radius

        backend = await get_backend(ctx, mode)
        fill_color, fill_shade = await resolve_color(
            backend, fill_color, fallback_shade=100, current_shade=fill_shade,
        )
        line_color, _ = await resolve_color(
            backend, line_color if line_color and line_color != "None" else None,
            fallback_color="None",
        )
        text_color, _ = await resolve_color(backend, text_color, fallback_color="White")

        body_parts = [
            "import scribus as _s",
            f"_circle = _s.createEllipse({rect_x}, {rect_y}, {diameter_mm}, {diameter_mm})",
            f"_s.setFillColor({fill_color!r}, _circle)",
        ]
        if fill_shade != 100:
            body_parts.append(f"_s.setFillShade({int(fill_shade)}, _circle)")
        if line_color and line_color != "None":
            body_parts.append(f"_s.setLineColor({line_color!r}, _circle)")
            body_parts.append(f"_s.setLineWidth({float(line_width_pt)}, _circle)")
        else:
            body_parts.append('_s.setLineColor("None", _circle)')
        body_parts.extend(
            [
                f"_text = _s.createText({rect_x}, {rect_y}, {diameter_mm}, {diameter_mm})",
                f"_s.setText({clean_user_text(str(text))!r}, _text)",
                f"_s.setFontSize({float(text_font_size_pt)}, _text)",
                f"_s.setTextColor({text_color!r}, _text)",
                "_s.setTextAlignment(1, _text)",
                "_s.setTextVerticalAlignment(1, _text)",
                '_value = {"circle": _circle, "text": _text}',
            ]
        )

        res = await backend.script("\n".join(body_parts) + "\n", result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "dot_label script failed"}
        out = res.value or {}
        return {
            "ok": True,
            "circle": out.get("circle"),
            "text": out.get("text"),
            "error": None,
        }

    @mcp.tool()
    async def create_numbered_badge(
        number: int,
        center_x_mm: float,
        center_y_mm: float,
        diameter_mm: float = 12.0,
        fill_color: str = "accent",
        text_color: str = "White",
        text_font_size_pt: float = 14.0,
        mode: Mode = "auto",
    ) -> dict:
        """Filled circle with a pixel-perfectly centered number.

        Two-step alignment: create circle + text frame, then convert the text
        to outline polygons (via ``traceText`` / ``outlineText``). Once the
        text is a polygon its ``getPosition`` + ``getSize`` return the *true
        glyph bbox*, not the original frame — so we can recenter that bbox
        exactly on the circle.

        Trade-off: the digit becomes a vector outline, not editable as text
        afterwards. For badges this is fine; the visual is the point.
        """
        if diameter_mm <= 0:
            return {"ok": False, "error": "diameter_mm must be > 0"}

        backend = await get_backend(ctx, mode)
        fill_color, _ = await resolve_color(backend, fill_color)
        text_color, _ = await resolve_color(backend, text_color, fallback_color="White")
        radius = diameter_mm / 2.0

        # Step 1: filled circle anchored at (center_x, center_y)
        cir = await backend.call(
            "createEllipse",
            center_x_mm - radius,
            center_y_mm - radius,
            diameter_mm,
            diameter_mm,
        )
        if not cir.ok:
            return {"ok": False, "error": f"circle failed: {cir.error}"}
        circle_name = cir.value
        await backend.call("setFillColor", fill_color, circle_name)
        await backend.call("setLineColor", "None", circle_name)

        # Step 2: the rest happens in a single Scripter script — create text
        # frame oversized so the digit isn't clipped, lay out, outline.
        # traceText REPLACES the text frame with one polygon per glyph
        # (named "<orig>+U0", "+U1", ...). Capture page items before and
        # after to find the new objects, then group them if multi-digit
        # so we have one bbox to recenter on the circle.
        body = (
            "import scribus as _s\n"
            # Force mm before any getSize / moveObjectAbs — those return /
            # consume values in the *current* doc unit, so a non-mm doc
            # would silently mis-center the digit.
            "try:\n"
            "    _s.setUnit(_s.UNIT_MILLIMETERS)\n"
            "except Exception:\n"
            "    pass\n"
            f"_play = {float(diameter_mm) * 2.5}\n"
            "_before = set(_it[0] for _it in (_s.getPageItems() or []))\n"
            f"_text = _s.createText({center_x_mm} - _play / 2, "
            f"{center_y_mm} - _play / 2, _play, _play)\n"
            f"_s.setText({str(int(number))!r}, _text)\n"
            f"_s.setFontSize({float(text_font_size_pt)}, _text)\n"
            f"_s.setTextColor({text_color!r}, _text)\n"
            "_s.setTextAlignment(1, _text)\n"
            "_s.setTextVerticalAlignment(1, _text)\n"
            "_s.layoutText(_text)\n"
            "_s.traceText(_text)\n"
            "_after = set(_it[0] for _it in (_s.getPageItems() or []))\n"
            "_new = sorted(_after - _before)\n"
            "if len(_new) == 0:\n"
            "    raise RuntimeError('traceText produced no objects')\n"
            "elif len(_new) == 1:\n"
            "    _final = _new[0]\n"
            "else:\n"
            "    _s.groupObjects(_new)\n"
            "    _post = set(_it[0] for _it in (_s.getPageItems() or []))\n"
            "    _grouped = sorted(_post - _before - set(_new))\n"
            "    _final = _grouped[-1] if _grouped else _new[0]\n"
            "_w, _h = _s.getSize(_final)\n"
            f"_s.moveObjectAbs({center_x_mm} - _w / 2, {center_y_mm} - _h / 2, _final)\n"
            "_value = {'name': _final, 'bbox': [_w, _h]}"
        )
        result = await backend.script(body, result_expr="_value")
        if not result.ok:
            return {
                "ok": False,
                "error": f"badge text outline failed: {result.error}",
                "circle": circle_name,
            }
        outline_info = result.value or {}
        return {
            "ok": True,
            "circle": circle_name,
            "text": outline_info.get("name"),
            "text_bbox_mm": outline_info.get("bbox"),
            "number": int(number),
            "error": None,
        }

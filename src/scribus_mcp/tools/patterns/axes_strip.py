"""Three-axes tall-card row — N parallel "pillars of the strategy" cards.

Each card frames one axis: large numeric eyebrow, multi-line title, italic
lead, bullet body, then a high-contrast dark "anchor" footer naming the
team or product driving the axis. Per-card accent color (typically 3
distinct colors for 3 axes).

Single-script-body design: every rect, text frame and font tweak is
emitted as one ``backend.script()`` round-trip.

Visual structure (per card)::

    ┌──────────────────────────────────┐  outer rounded rect, surface fill
    │ ████████████████████████████████ │
    │ ██  01                       ██  │  colored header — number, title,
    │ ██  Axis title (multi-line)  ██  │  italic lead. Rounded top corners,
    │ ██  short italic lead        ██  │  squared bottom seam against the body.
    │ ████████████████████████████████ │
    │  • bullet 1                      │
    │  • bullet 2                      │  body bullets
    │  • bullet 3                      │
    │ ████████████████████████████████ │  dark anchor footer — eyebrow + name.
    │  ANCRAGE                         │  Rounded bottom corners, squared top
    │  Team / product name             │  seam against the body.
    └──────────────────────────────────┘

Geometry: ``card_w = (width_mm - (columns-1)*gap_mm) / columns``;
``card_h`` is ``height_mm`` directly. Rounded corners on the outer rect
and the header / footer; a second flat rect at each seam squares the
inside edges so corners only appear on the card's outer perimeter.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes
from scribus_mcp.tools.palette import resolve_color


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_axes_strip(
        items: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 200.0,
        columns: int = 3,
        gap_mm: float = 4.0,
        header_height_mm: float = 56.0,
        footer_height_mm: float = 16.0,
        padding_mm: float = 6.0,
        corner_radius_mm: float = 2.0,
        # Fonts. Empty string = use the document default font face. Bold
        # / italic variants of DejaVu Sans (the Scribus default) ship on
        # every standard Linux install; pass other names if the document
        # uses a different family.
        number_font: str = "DejaVu Sans Bold",
        title_font: str = "DejaVu Sans Bold",
        lead_font: str = "DejaVu Sans Oblique",
        body_font: str = "",
        eyebrow_font: str = "DejaVu Sans Bold",
        anchor_font: str = "DejaVu Sans Bold",
        # Sizes
        number_font_size_pt: float = 34.0,
        title_font_size_pt: float = 13.0,
        title_line_spacing_pt: float = 15.0,
        lead_font_size_pt: float = 9.0,
        body_font_size_pt: float = 9.5,
        body_line_spacing_pt: float = 14.0,
        eyebrow_font_size_pt: float = 7.0,
        anchor_font_size_pt: float = 9.0,
        # Color slots — palette roles accepted everywhere.
        fill_color: str = "surface",
        fill_shade: int | None = None,
        border_color: str = "muted",
        border_shade: int | None = None,
        border_width_pt: float = 0.4,
        footer_color: str = "ink",
        number_color: str = "White",
        title_color: str = "White",
        lead_color: str = "ink",
        body_color: str = "muted",
        anchor_name_color: str = "White",
        bullet_marker: str = "•",
        mode: Mode = "auto",
    ) -> dict:
        """Render N tall "axes" cards side by side, one per item.

        Each item is a dict with:
            number       — short label rendered very large at the top of
                           the colored header (e.g. ``"01"``, ``"02"``).
            title        — multi-line axis title; embed ``\\n`` for line
                           breaks. Bold over the colored header.
            lead         — short italic lead under the title (optional).
            items        — list of bullet strings; each renders as
                           ``"• <text>"``.
            anchor       — the team / product driving the axis,
                           rendered bold-on-dark in the footer.
            anchor_eyebrow — small-caps label above the anchor name
                           (default ``"ANCRAGE"``).
            accent_color — header fill color for this card; also used
                           for the anchor eyebrow. Palette roles accepted.

        ``columns`` defaults to 3 — the canonical "three pillars"
        layout. The pattern works at any ``columns`` value; with N=4 or
        more, drop ``number_font_size_pt`` and ``title_font_size_pt``
        to fit narrower cards.

        Color slots default to palette roles — define ``surface``,
        ``muted``, ``ink`` once and the chrome adopts them. The
        per-item ``accent_color`` is per-card and sits on top.

        Returns ``{ok, cards: [{outer, header, header_seam, number,
        title, lead, bullets, footer, footer_seam, eyebrow, name}],
        bbox}``.
        """
        if not items:
            return {"ok": False, "error": "items must not be empty"}
        if columns < 1:
            return {"ok": False, "error": "columns must be >= 1"}
        for i, it in enumerate(items):
            for key in ("number", "title", "items", "anchor", "accent_color"):
                if key not in it:
                    return {"ok": False, "error": f"item {i} missing {key!r}"}
            if not isinstance(it["items"], list):
                return {"ok": False, "error": f"item {i} 'items' must be a list"}

        bboxes = compute_column_bboxes(
            x_mm, y_mm, width_mm, height_mm, columns, gap_mm
        )
        if not bboxes:
            return {
                "ok": False,
                "error": (
                    f"width_mm ({width_mm}) too small for {columns} columns "
                    f"with gap {gap_mm}"
                ),
            }
        # Cap the items list to ``columns``; extra items fall off the
        # right edge silently rather than overflowing the page.
        items = list(items)[:columns]

        backend = await get_backend(ctx, mode)
        fill_color, fill_shade = await resolve_color(
            backend, fill_color, fallback_shade=100, current_shade=fill_shade,
        )
        border_color, border_shade = await resolve_color(
            backend, border_color, fallback_shade=25, current_shade=border_shade,
        )
        footer_color, _ = await resolve_color(backend, footer_color)
        number_color, _ = await resolve_color(backend, number_color, fallback_color="White")
        title_color, _ = await resolve_color(backend, title_color, fallback_color="White")
        lead_color, _ = await resolve_color(backend, lead_color)
        body_color, _ = await resolve_color(backend, body_color)
        anchor_name_color, _ = await resolve_color(
            backend, anchor_name_color, fallback_color="White",
        )
        # Per-item accent — resolved once per card so the script body
        # carries literal color names.
        accent_colors: list[str] = []
        for it in items:
            ac, _ = await resolve_color(backend, str(it["accent_color"]))
            accent_colors.append(ac)

        # ---- Build the spec lists per card --------------------------------
        cards_spec: list[dict] = []
        for i, (it, bbox) in enumerate(zip(items, bboxes, strict=False)):
            cx, cy = bbox["x_mm"], bbox["y_mm"]
            cw = bbox["width_mm"]
            ch = float(height_mm)
            head_h = float(header_height_mm)
            foot_h = float(footer_height_mm)
            pad = float(padding_mm)
            r = float(corner_radius_mm)
            seam = max(2.0, r * 4.0)  # the "square the seam" overlay rect height
            # Body bullet text — each line prefixed with the marker.
            body_lines = [f"{bullet_marker} {clean_user_text(str(b))}" for b in it["items"]]
            cards_spec.append(
                {
                    "outer": (cx, cy, cw, ch),
                    "header": (cx, cy, cw, head_h),
                    "header_seam": (cx, cy + head_h - seam, cw, seam),
                    "number": (
                        cx + pad, cy + pad,
                        cw - 2 * pad,
                        max(12.0, number_font_size_pt * 0.6),
                        clean_user_text(str(it["number"])),
                    ),
                    "title": (
                        cx + pad, cy + pad + 22.0,
                        cw - 2 * pad,
                        18.0,
                        clean_user_text(str(it["title"])),
                    ),
                    "lead": (
                        cx + pad, cy + head_h - 12.0,
                        cw - 2 * pad,
                        11.0,
                        clean_user_text(str(it.get("lead", ""))),
                    ),
                    "body": (
                        cx + pad, cy + head_h + pad,
                        cw - 2 * pad,
                        ch - head_h - pad - foot_h - 2.0,
                        "\n".join(body_lines),
                    ),
                    "footer": (cx, cy + ch - foot_h, cw, foot_h),
                    "footer_seam": (cx, cy + ch - foot_h, cw, seam),
                    "eyebrow": (
                        cx + pad, cy + ch - foot_h + 2.0,
                        cw - 2 * pad,
                        4.5,
                        clean_user_text(str(it.get("anchor_eyebrow", "ANCRAGE"))).upper(),
                    ),
                    "name": (
                        cx + pad, cy + ch - foot_h + 7.0,
                        cw - 2 * pad,
                        8.0,
                        clean_user_text(str(it["anchor"])),
                    ),
                    "accent": accent_colors[i],
                }
            )

        body = f"""
import scribus as _s


def _try_set_font(_obj, _name):
    if not _name:
        return
    try:
        _s.setFont(_name, _obj)
    except Exception:
        pass  # font may not be installed; fall back to document default


_cards = []
for _spec in {cards_spec!r}:
    _ox, _oy, _ow, _oh = _spec["outer"]
    _outer = _s.createRect(_ox, _oy, _ow, _oh)
    _s.setFillColor({fill_color!r}, _outer)
    _s.setFillShade({int(fill_shade)}, _outer)
    _s.setLineColor({border_color!r}, _outer)
    _s.setLineShade({int(border_shade)}, _outer)
    _s.setLineWidth({float(border_width_pt)}, _outer)
    try:
        _s.setCornerRadius({round(float(corner_radius_mm) * 2.834645669)}, _outer)
    except Exception:
        pass

    _hx, _hy, _hw, _hh = _spec["header"]
    _header = _s.createRect(_hx, _hy, _hw, _hh)
    _s.setFillColor(_spec["accent"], _header)
    _s.setLineColor("None", _header)
    try:
        _s.setCornerRadius({round(float(corner_radius_mm) * 2.834645669)}, _header)
    except Exception:
        pass

    _sx, _sy, _sw, _sh = _spec["header_seam"]
    _hseam = _s.createRect(_sx, _sy, _sw, _sh)
    _s.setFillColor(_spec["accent"], _hseam)
    _s.setLineColor("None", _hseam)

    _nx, _ny, _nw, _nh, _ntext = _spec["number"]
    _number = _s.createText(_nx, _ny, _nw, _nh)
    _s.setText(_ntext, _number)
    _s.setFontSize({float(number_font_size_pt)}, _number)
    _s.setTextColor({number_color!r}, _number)
    _try_set_font(_number, {number_font!r})

    _tx, _ty, _tw, _th, _ttext = _spec["title"]
    _title = _s.createText(_tx, _ty, _tw, _th)
    _s.setText(_ttext, _title)
    _s.setFontSize({float(title_font_size_pt)}, _title)
    _s.setTextColor({title_color!r}, _title)
    try:
        _s.setLineSpacing({float(title_line_spacing_pt)}, _title)
    except Exception:
        pass
    _try_set_font(_title, {title_font!r})

    _lx, _ly, _lw, _lh, _ltext = _spec["lead"]
    _lead = _s.createText(_lx, _ly, _lw, _lh)
    _s.setText(_ltext, _lead)
    _s.setFontSize({float(lead_font_size_pt)}, _lead)
    _s.setTextColor({lead_color!r}, _lead)
    _try_set_font(_lead, {lead_font!r})

    _bx, _by, _bw, _bh, _btext = _spec["body"]
    _body = _s.createText(_bx, _by, _bw, _bh)
    _s.setText(_btext, _body)
    _s.setFontSize({float(body_font_size_pt)}, _body)
    _s.setTextColor({body_color!r}, _body)
    try:
        _s.setLineSpacing({float(body_line_spacing_pt)}, _body)
    except Exception:
        pass
    _try_set_font(_body, {body_font!r})

    _fx, _fy, _fw, _fh = _spec["footer"]
    _footer = _s.createRect(_fx, _fy, _fw, _fh)
    _s.setFillColor({footer_color!r}, _footer)
    _s.setLineColor("None", _footer)
    try:
        _s.setCornerRadius({round(float(corner_radius_mm) * 2.834645669)}, _footer)
    except Exception:
        pass

    _fsx, _fsy, _fsw, _fsh = _spec["footer_seam"]
    _fseam = _s.createRect(_fsx, _fsy, _fsw, _fsh)
    _s.setFillColor({footer_color!r}, _fseam)
    _s.setLineColor("None", _fseam)

    _ex, _ey, _ew, _eh, _etext = _spec["eyebrow"]
    _eyebrow = _s.createText(_ex, _ey, _ew, _eh)
    _s.setText(_etext, _eyebrow)
    _s.setFontSize({float(eyebrow_font_size_pt)}, _eyebrow)
    _s.setTextColor(_spec["accent"], _eyebrow)
    _try_set_font(_eyebrow, {eyebrow_font!r})

    _ax, _ay, _aw, _ah, _atext = _spec["name"]
    _name = _s.createText(_ax, _ay, _aw, _ah)
    _s.setText(_atext, _name)
    _s.setFontSize({float(anchor_font_size_pt)}, _name)
    _s.setTextColor({anchor_name_color!r}, _name)
    _try_set_font(_name, {anchor_font!r})

    _cards.append({{
        "outer": _outer,
        "header": _header,
        "header_seam": _hseam,
        "number": _number,
        "title": _title,
        "lead": _lead,
        "body": _body,
        "footer": _footer,
        "footer_seam": _fseam,
        "eyebrow": _eyebrow,
        "name": _name,
    }})

_value = {{"cards": _cards}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "axes_strip script failed"}

        out = res.value or {}
        return {
            "ok": True,
            "cards": out.get("cards", []),
            "count": len(items),
            "card_width_mm": bboxes[0]["width_mm"],
            "bbox": {
                "x_mm": x_mm,
                "y_mm": y_mm,
                "width_mm": width_mm,
                "height_mm": float(height_mm),
            },
            "error": None,
        }

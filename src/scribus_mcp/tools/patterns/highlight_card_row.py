"""Series cards with a high-contrast highlight strap at the bottom.

A pair (or small grid) of medium cards each promoting a "series in
production" / "shipped product" message. Card carries a title, a prose
body, and a colored strap at the bottom that surfaces the single most
important metric — the fact you want the reader to remember after
scanning.

Differs from ``axes_strip`` (full anchor footer with eyebrow + name)
and ``pillar_strip`` (3 stacked proofs + body): the strap here is a
single bold statement, not a structured stack.

Single-script-body design.

Visual structure (per card)::

    ┌────────────────────────────────────────────┐
    │  Title (bold)                              │
    │                                            │
    │  Body paragraph — 9.5 pt, leading 13,      │
    │  muted color, justified or left-aligned.   │
    │  May span several lines.                   │
    │                                            │
    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │   bottom strap, accent fill
    │  Highlight statement — 10 pt bold, ink     │
    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
    └────────────────────────────────────────────┘
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes
from scribus_mcp.tools.palette import resolve_color


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_highlight_card_row(
        items: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 58.0,
        columns: int = 2,
        gap_mm: float = 4.0,
        padding_mm: float = 4.0,
        corner_radius_mm: float = 2.0,
        # Geometry
        title_height_mm: float = 8.0,
        strap_height_mm: float = 9.0,
        # Borders
        border_width_pt: float = 0.5,
        # Fonts
        title_font: str = "DejaVu Sans Bold",
        body_font: str = "",
        strap_font: str = "DejaVu Sans Bold",
        # Sizes
        title_font_size_pt: float = 12.0,
        body_font_size_pt: float = 9.5,
        body_line_spacing_pt: float = 13.0,
        strap_font_size_pt: float = 10.0,
        # Color slots — palette roles accepted
        accent_color: str = "accent",
        fill_color: str = "surface",
        fill_shade: int | None = None,
        title_color: str = "ink",
        body_color: str = "muted",
        strap_text_color: str = "ink",
        body_alignment: str = "left",
        mode: Mode = "auto",
    ) -> dict:
        """Render N cards side by side with title + body + accent strap.

        ``items`` is a list of dicts with:
            title       — bold ink card title (required)
            body        — prose paragraph below the title (required)
            highlight   — short statement rendered bold-on-accent at
                          the bottom of the card (required)
            accent_color — per-card accent driving the border + strap
                          (optional — falls back to the table-level
                          ``accent_color``). Palette roles accepted.

        Returns ``{ok, cards: [{outer, title, body, strap, highlight}],
        bbox}``.
        """
        if not items:
            return {"ok": False, "error": "items must not be empty"}
        if columns < 1:
            return {"ok": False, "error": "columns must be >= 1"}
        for i, it in enumerate(items):
            for k in ("title", "body", "highlight"):
                if k not in it:
                    return {"ok": False, "error": f"item {i} missing {k!r}"}

        align_map = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}
        if body_alignment not in align_map:
            return {
                "ok": False,
                "error": f"body_alignment must be one of {sorted(align_map)}",
            }

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
        items = list(items)[:columns]

        backend = await get_backend(ctx, mode)
        accent_color, _ = await resolve_color(backend, accent_color)
        fill_color, fill_shade = await resolve_color(
            backend, fill_color, fallback_shade=8, current_shade=fill_shade,
        )
        title_color, _ = await resolve_color(backend, title_color)
        body_color, _ = await resolve_color(backend, body_color)
        strap_text_color, _ = await resolve_color(backend, strap_text_color)

        # Per-item accent (falls back to the table-level value).
        item_accents: list[str] = []
        for it in items:
            override = it.get("accent_color")
            if override:
                ac, _ = await resolve_color(backend, str(override))
                item_accents.append(ac)
            else:
                item_accents.append(accent_color)

        cards_spec: list[dict] = []
        for i, (it, bbox) in enumerate(zip(items, bboxes, strict=False)):
            cx, cy = bbox["x_mm"], bbox["y_mm"]
            cw = bbox["width_mm"]
            ch = float(height_mm)
            pad = float(padding_mm)
            inner_w = cw - 2 * pad
            title_y = cy + pad
            body_y = title_y + float(title_height_mm) + 1.0
            body_h = ch - float(title_height_mm) - float(strap_height_mm) - 2 * pad - 1.0
            strap_y = cy + ch - float(strap_height_mm)
            cards_spec.append(
                {
                    "outer": (cx, cy, cw, ch),
                    "title": (
                        cx + pad, title_y, inner_w, float(title_height_mm),
                        clean_user_text(str(it["title"])),
                    ),
                    "body": (
                        cx + pad, body_y, inner_w, max(8.0, body_h),
                        clean_user_text(str(it["body"])),
                    ),
                    "strap": (cx, strap_y, cw, float(strap_height_mm)),
                    "highlight": (
                        cx + pad, strap_y + 0.5,
                        inner_w, float(strap_height_mm) - 1.0,
                        clean_user_text(str(it["highlight"])),
                    ),
                    "accent": item_accents[i],
                }
            )

        radius_pt = round(float(corner_radius_mm) * 2.834645669)

        body = f"""
import scribus as _s


def _try_set_font(_obj, _name):
    if not _name:
        return
    try:
        _s.setFont(_name, _obj)
    except Exception:
        pass


_cards = []
for _spec in {cards_spec!r}:
    _ox, _oy, _ow, _oh = _spec["outer"]
    _outer = _s.createRect(_ox, _oy, _ow, _oh)
    _s.setFillColor({fill_color!r}, _outer)
    _s.setFillShade({int(fill_shade)}, _outer)
    _s.setLineColor(_spec["accent"], _outer)
    _s.setLineWidth({float(border_width_pt)}, _outer)
    try:
        _s.setCornerRadius({radius_pt}, _outer)
    except Exception:
        pass

    _tx, _ty, _tw, _th, _ttext = _spec["title"]
    _title = _s.createText(_tx, _ty, _tw, _th)
    _s.setText(_ttext, _title)
    _s.setFontSize({float(title_font_size_pt)}, _title)
    _s.setTextColor({title_color!r}, _title)
    _try_set_font(_title, {title_font!r})

    _bx, _by, _bw, _bh, _btext = _spec["body"]
    _body = _s.createText(_bx, _by, _bw, _bh)
    _s.setText(_btext, _body)
    _s.setFontSize({float(body_font_size_pt)}, _body)
    _s.setTextColor({body_color!r}, _body)
    try:
        _s.setLineSpacing({float(body_line_spacing_pt)}, _body)
    except Exception:
        pass
    _s.setTextAlignment({align_map[body_alignment]}, _body)
    _try_set_font(_body, {body_font!r})

    _sx, _sy, _sw, _sh = _spec["strap"]
    _strap = _s.createRect(_sx, _sy, _sw, _sh)
    _s.setFillColor(_spec["accent"], _strap)
    _s.setLineColor("None", _strap)
    try:
        _s.setCornerRadius({radius_pt}, _strap)
    except Exception:
        pass

    _hx, _hy, _hw, _hh, _htext = _spec["highlight"]
    _hl = _s.createText(_hx, _hy, _hw, _hh)
    _s.setText(_htext, _hl)
    _s.setFontSize({float(strap_font_size_pt)}, _hl)
    _s.setTextColor({strap_text_color!r}, _hl)
    _s.setTextVerticalAlignment(1, _hl)
    _try_set_font(_hl, {strap_font!r})

    _cards.append({{
        "outer": _outer,
        "title": _title,
        "body": _body,
        "strap": _strap,
        "highlight": _hl,
    }})

_value = {{"cards": _cards}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {
                "ok": False,
                "error": res.error or "highlight_card_row script failed",
            }

        out = res.value or {}
        return {
            "ok": True,
            "cards": out.get("cards", []),
            "count": len(items),
            "card_width_mm": bboxes[0]["width_mm"],
            "bbox": {
                "x_mm": float(x_mm),
                "y_mm": float(y_mm),
                "width_mm": float(width_mm),
                "height_mm": float(height_mm),
            },
            "error": None,
        }

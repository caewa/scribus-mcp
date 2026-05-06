"""Three-pillars tall-card row — claim · evidence · narrative.

White cards with colored borders. Per pillar: giant accent-coloured
number, multi-line title, italic lead, accent separator, three stacked
proof rows (value + label), then a prose body. Compared to
``axes_strip`` (which fronts each axis with a colored header and an
ink-coloured anchor footer), this pattern is austere: the only color
beats are the number, the lead, the separator and the border — useful
when the surrounding deck already carries a lot of color.

Single-script-body design.

Visual structure (per card)::

    ┌──────────────────────────────────┐
    │                                  │
    │  01                              │   giant number, accent color
    │  Pillar title (multi-line)       │   bold ink
    │  Italic lead                     │   italic, accent color
    │ ───────────────────────────────  │   accent separator
    │  > 1 000                         │   proof 1 value (black, accent)
    │  boîtiers en flotte              │   proof 1 label (bold, muted)
    │  Taux SAV                        │   proof 2 ...
    │  résiduel                        │
    │  2 séries                        │   proof 3 ...
    │  100% MUXen                      │
    │                                  │
    │  Plate-forme HW propriétaire,    │   prose body, muted, justified
    │  …                               │
    └──────────────────────────────────┘
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_pillar_strip(
        items: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 170.0,
        columns: int = 3,
        gap_mm: float = 4.0,
        padding_mm: float = 6.0,
        corner_radius_mm: float = 2.0,
        # Geometry
        number_block_height_mm: float = 22.0,
        title_block_height_mm: float = 12.0,
        lead_block_height_mm: float = 10.0,
        separator_offset_mm: float = 2.0,  # gap above the separator
        proof_row_height_mm: float = 16.0,
        proof_count: int = 3,
        # Borders / lines
        border_width_pt: float = 1.0,
        separator_width_pt: float = 0.6,
        # Fonts
        number_font: str = "DejaVu Sans Bold",
        title_font: str = "DejaVu Sans Bold",
        lead_font: str = "DejaVu Sans Oblique",
        proof_value_font: str = "DejaVu Sans Bold",
        proof_label_font: str = "DejaVu Sans Bold",
        body_font: str = "",
        # Sizes
        number_font_size_pt: float = 42.0,
        title_font_size_pt: float = 14.0,
        title_line_spacing_pt: float = 16.0,
        lead_font_size_pt: float = 10.0,
        lead_line_spacing_pt: float = 12.0,
        proof_value_font_size_pt: float = 14.0,
        proof_label_font_size_pt: float = 8.0,
        body_font_size_pt: float = 9.0,
        body_line_spacing_pt: float = 12.5,
        # Color slots — palette roles accepted
        fill_color: str = "White",
        title_color: str = "ink",
        proof_label_color: str = "muted",
        body_color: str = "muted",
        body_alignment: str = "justify",
        mode: Mode = "auto",
    ) -> dict:
        """Render N pillar cards side by side, one per item.

        Each item is a dict with:
            number       — giant accent-coloured eyebrow at the top
                           (e.g. ``"01"``).
            title        — bold ink title; embed ``\\n`` for line
                           breaks.
            lead         — italic accent-coloured lead under the title
                           (optional).
            proofs       — list of ``[value, label]`` pairs (typically
                           three). Each renders as a value (black,
                           accent color) above its label (bold, muted).
            body         — prose paragraph below the proofs (optional).
            accent_color — per-pillar accent driving the number, the
                           lead, the separator and the border. Palette
                           roles accepted.

        ``columns`` defaults to 3 — the canonical "three pillars"
        layout. ``proof_count`` (default 3) controls how many proof
        rows the layout reserves; pad shorter ``proofs`` lists with
        empty pairs to fill the grid.

        Returns ``{ok, cards: [{outer, number, title, lead, separator,
        proofs:[{value,label}], body}], bbox}``.
        """
        if not items:
            return {"ok": False, "error": "items must not be empty"}
        if columns < 1:
            return {"ok": False, "error": "columns must be >= 1"}
        for i, it in enumerate(items):
            for key in ("number", "title", "proofs", "accent_color"):
                if key not in it:
                    return {"ok": False, "error": f"item {i} missing {key!r}"}
            if not isinstance(it["proofs"], list):
                return {"ok": False, "error": f"item {i} 'proofs' must be a list"}

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
        fill_color, _ = await resolve_color(backend, fill_color, fallback_color="White")
        title_color, _ = await resolve_color(backend, title_color)
        proof_label_color, _ = await resolve_color(backend, proof_label_color)
        body_color, _ = await resolve_color(backend, body_color)
        accent_colors: list[str] = []
        for it in items:
            ac, _ = await resolve_color(backend, str(it["accent_color"]))
            accent_colors.append(ac)

        # Pre-compute geometry per card.
        cards_spec: list[dict] = []
        for i, (it, bbox) in enumerate(zip(items, bboxes, strict=False)):
            cx, cy = bbox["x_mm"], bbox["y_mm"]
            cw = bbox["width_mm"]
            ch = float(height_mm)
            pad = float(padding_mm)
            inner_w = cw - 2 * pad

            # Vertical layout — same offsets the spec lays out.
            num_y = cy + pad
            title_y = num_y + float(number_block_height_mm) + 4.0
            lead_y = title_y + float(title_block_height_mm) + 6.0
            sep_y = lead_y + float(lead_block_height_mm) + float(separator_offset_mm)
            proofs_y = sep_y + 4.0

            # Pad proofs to ``proof_count`` so each card reserves the
            # same vertical space (keeps multi-card rows visually
            # aligned even when one card has fewer proofs).
            proofs_in = list(it["proofs"]) + [["", ""]] * proof_count
            proofs_in = proofs_in[:proof_count]
            proofs_spec = []
            for j, pair in enumerate(proofs_in):
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    val, lbl = str(pair[0]), str(pair[1])
                else:
                    val, lbl = "", ""
                py = proofs_y + j * float(proof_row_height_mm)
                proofs_spec.append(
                    (
                        py, clean_user_text(val), clean_user_text(lbl),
                    )
                )

            body_y = proofs_y + proof_count * float(proof_row_height_mm) + 4.0
            body_h = max(8.0, ch - (body_y - cy) - pad)

            cards_spec.append(
                {
                    "outer": (cx, cy, cw, ch),
                    "number": (
                        cx + pad, num_y, inner_w,
                        float(number_block_height_mm),
                        clean_user_text(str(it["number"])),
                    ),
                    "title": (
                        cx + pad, title_y, inner_w,
                        float(title_block_height_mm),
                        clean_user_text(str(it["title"])),
                    ),
                    "lead": (
                        cx + pad, lead_y, inner_w,
                        float(lead_block_height_mm),
                        clean_user_text(str(it.get("lead", ""))),
                    ),
                    "separator": (
                        cx + pad, sep_y, cx + cw - pad, sep_y,
                    ),
                    "proofs": proofs_spec,
                    "proof_x": cx + pad,
                    "proof_w": inner_w,
                    "body": (
                        cx + pad, body_y, inner_w, body_h,
                        clean_user_text(str(it.get("body", ""))),
                    ),
                    "accent": accent_colors[i],
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
    _s.setLineColor(_spec["accent"], _outer)
    _s.setLineWidth({float(border_width_pt)}, _outer)
    try:
        _s.setCornerRadius({radius_pt}, _outer)
    except Exception:
        pass

    _nx, _ny, _nw, _nh, _ntext = _spec["number"]
    _number = _s.createText(_nx, _ny, _nw, _nh)
    _s.setText(_ntext, _number)
    _s.setFontSize({float(number_font_size_pt)}, _number)
    _s.setTextColor(_spec["accent"], _number)
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
    _s.setTextColor(_spec["accent"], _lead)
    try:
        _s.setLineSpacing({float(lead_line_spacing_pt)}, _lead)
    except Exception:
        pass
    _try_set_font(_lead, {lead_font!r})

    _sx1, _sy1, _sx2, _sy2 = _spec["separator"]
    _sep = _s.createLine(_sx1, _sy1, _sx2, _sy2)
    _s.setLineColor(_spec["accent"], _sep)
    _s.setLineWidth({float(separator_width_pt)}, _sep)

    _proofs = []
    _px, _pw = _spec["proof_x"], _spec["proof_w"]
    for _py, _val, _lbl in _spec["proofs"]:
        _vt = _s.createText(_px, _py, _pw, 8.0)
        _s.setText(_val, _vt)
        _s.setFontSize({float(proof_value_font_size_pt)}, _vt)
        _s.setTextColor(_spec["accent"], _vt)
        _try_set_font(_vt, {proof_value_font!r})

        _lt = _s.createText(_px, _py + 8.0, _pw, 6.0)
        _s.setText(_lbl, _lt)
        _s.setFontSize({float(proof_label_font_size_pt)}, _lt)
        _s.setTextColor({proof_label_color!r}, _lt)
        _try_set_font(_lt, {proof_label_font!r})

        _proofs.append({{"value": _vt, "label": _lt}})

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

    _cards.append({{
        "outer": _outer,
        "number": _number,
        "title": _title,
        "lead": _lead,
        "separator": _sep,
        "proofs": _proofs,
        "body": _body,
    }})

_value = {{"cards": _cards}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "pillar_strip script failed"}

        out = res.value or {}
        members: list[str | None] = []
        for card in out.get("cards", []) or []:
            if isinstance(card, dict):
                members.extend(card.values())
        group_name = await group_created_objects(backend, members)
        return {
            "ok": True,
            "cards": out.get("cards", []),
            "group": group_name,
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

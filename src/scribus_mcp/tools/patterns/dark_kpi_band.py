"""Dark KPI band — one giant headline number + horizontal breakdown.

Compact (~42 mm tall) full-width band: rounded dark fill, eyebrow title at
the top, big number + caption on the left, then 2-4 breakdown rows on the
right with mini progress bars showing each row's share. Suits "footprint",
"totals", "spend", "energy mix" slides where the headline number needs an
instant decomposition without a separate chart.

Single-script-body design: every rect + text is emitted as one
``backend.script()`` round-trip.

Visual structure::

    ┌────────────────────────────────────────────────────────────────┐
    │  Title — small caps eyebrow, accent color                      │
    │                                                                │
    │  117 556        Carburant                  73 318 t      62 %  │
    │                 ███████████████████████████████░░░░░░░░        │
    │  tCO2e total    Électricité                18 402 t      16 %  │
    │                 ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░         │
    │                 Maintenance / équip.       25 836 t      22 %  │
    │                 ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░         │
    └────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_dark_kpi_band(
        title: str,
        headline_value: str,
        headline_caption: str,
        breakdown: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 42.0,
        padding_mm: float = 6.0,
        corner_radius_mm: float = 2.0,
        # Geometry
        title_height_mm: float = 6.0,
        headline_column_width_mm: float = 70.0,
        row_height_mm: float = 9.0,
        bar_height_mm: float = 1.6,
        bar_offset_mm: float = 5.5,
        # Colors (palette roles accepted)
        fill_color: str = "ink",
        fill_shade: int | None = None,
        title_color: str = "accent",
        headline_color: str = "White",
        caption_color: str = "accent",
        label_color: str = "White",
        value_color: str = "White",
        bar_track_color: str = "muted",
        bar_track_shade: int | None = None,
        # Fonts
        title_font: str = "DejaVu Sans Bold",
        title_font_size_pt: float = 11.0,
        headline_font: str = "DejaVu Sans Bold",
        headline_font_size_pt: float = 26.0,
        caption_font_size_pt: float = 8.5,
        label_font: str = "DejaVu Sans Bold",
        label_font_size_pt: float = 9.0,
        value_font_size_pt: float = 9.0,
        percent_font: str = "DejaVu Sans Bold",
        percent_font_size_pt: float = 9.0,
        mode: Mode = "auto",
    ) -> dict:
        """Render a dark KPI band with a left-aligned headline number and
        a right-aligned breakdown of N rows with progress bars.

        ``breakdown`` is a list of dicts with:
            label   — the contributing row's name (bold, light text)
            value   — short text right-aligned next to the label
                      (e.g. ``"73 318 t"``)
            percent — number 0..100 — drives the progress bar fill width
            color   — per-row accent for the bar fill + the percent text;
                      palette roles accepted

        ``headline_caption`` renders under the big number in the accent
        color — typical use is to spell out the unit / scope (e.g.
        ``"tCO2e total (usage)"``).

        Color slots default to palette roles — define ``ink``,
        ``accent``, ``muted`` once and the band adopts them. Returns
        ``{ok, background, title, headline, caption, rows, bbox}``.
        """
        if not breakdown:
            return {"ok": False, "error": "breakdown must not be empty"}
        if not 1 <= len(breakdown) <= 6:
            return {"ok": False, "error": "breakdown must have 1..6 rows"}
        for i, row in enumerate(breakdown):
            for k in ("label", "value", "percent", "color"):
                if k not in row:
                    return {"ok": False, "error": f"breakdown[{i}] missing {k!r}"}
            try:
                pct = float(row["percent"])
            except (TypeError, ValueError):
                return {
                    "ok": False,
                    "error": f"breakdown[{i}] 'percent' must be a number 0..100",
                }
            if not 0.0 <= pct <= 100.0:
                return {
                    "ok": False,
                    "error": f"breakdown[{i}] 'percent' must be in [0, 100]",
                }

        backend = await get_backend(ctx, mode)
        fill_color, fill_shade = await resolve_color(
            backend, fill_color, fallback_shade=100, current_shade=fill_shade,
        )
        title_color, _ = await resolve_color(backend, title_color)
        headline_color, _ = await resolve_color(backend, headline_color, fallback_color="White")
        caption_color, _ = await resolve_color(backend, caption_color)
        label_color, _ = await resolve_color(backend, label_color, fallback_color="White")
        value_color, _ = await resolve_color(backend, value_color, fallback_color="White")
        bar_track_color, bar_track_shade = await resolve_color(
            backend, bar_track_color, fallback_shade=30, current_shade=bar_track_shade,
        )
        # Per-row accent: resolved once each so the script body has literals.
        rows_resolved: list[dict] = []
        for row in breakdown:
            rc, _ = await resolve_color(backend, str(row["color"]))
            rows_resolved.append(
                {
                    "label": clean_user_text(str(row["label"])),
                    "value": clean_user_text(str(row["value"])),
                    "percent": float(row["percent"]),
                    "color": rc,
                }
            )

        # Geometry — pre-compute everything Python-side.
        bx = float(x_mm) + float(headline_column_width_mm) + float(padding_mm)
        bw = float(width_mm) - float(headline_column_width_mm) - 2 * float(padding_mm)
        # Stack rows starting just below the title strip, with constant
        # row_height_mm. Caller's height_mm is the band's overall height —
        # we don't auto-size, so a tall band with few rows leaves space at
        # the bottom (intentional — the band sits among other elements).
        rows_y0 = float(y_mm) + float(title_height_mm) + 6.0
        radius_pt = round(float(corner_radius_mm) * 2.834645669)
        bar_radius_pt = round(0.4 * 2.834645669)

        body = f"""
import scribus as _s


def _try_set_font(_obj, _name):
    if not _name:
        return
    try:
        _s.setFont(_name, _obj)
    except Exception:
        pass


# Background band
_bg = _s.createRect({float(x_mm)}, {float(y_mm)}, {float(width_mm)}, {float(height_mm)})
_s.setFillColor({fill_color!r}, _bg)
_s.setFillShade({int(fill_shade)}, _bg)
_s.setLineColor("None", _bg)
try:
    _s.setCornerRadius({radius_pt}, _bg)
except Exception:
    pass

# Title eyebrow
_title = _s.createText(
    {float(x_mm) + float(padding_mm)}, {float(y_mm) + 4.0},
    {float(width_mm) - 2 * float(padding_mm)}, {float(title_height_mm)},
)
_s.setText({clean_user_text(str(title))!r}, _title)
_s.setFontSize({float(title_font_size_pt)}, _title)
_s.setTextColor({title_color!r}, _title)
_try_set_font(_title, {title_font!r})

# Big headline number
_headline = _s.createText(
    {float(x_mm) + float(padding_mm)}, {float(y_mm) + float(title_height_mm) + 6.0},
    {float(headline_column_width_mm) - float(padding_mm)}, 14.0,
)
_s.setText({clean_user_text(str(headline_value))!r}, _headline)
_s.setFontSize({float(headline_font_size_pt)}, _headline)
_s.setTextColor({headline_color!r}, _headline)
_try_set_font(_headline, {headline_font!r})

# Caption under the number
_caption = _s.createText(
    {float(x_mm) + float(padding_mm)},
    {float(y_mm) + float(title_height_mm) + 22.0},
    {float(headline_column_width_mm) - float(padding_mm)}, 6.0,
)
_s.setText({clean_user_text(str(headline_caption))!r}, _caption)
_s.setFontSize({float(caption_font_size_pt)}, _caption)
_s.setTextColor({caption_color!r}, _caption)

# Breakdown rows
_rows = []
for _i, _row in enumerate({rows_resolved!r}):
    _by = {rows_y0} + _i * {float(row_height_mm)}

    _label = _s.createText({bx}, _by, {bw} * 0.55, 4.5)
    _s.setText(_row["label"], _label)
    _s.setFontSize({float(label_font_size_pt)}, _label)
    _s.setTextColor({label_color!r}, _label)
    _try_set_font(_label, {label_font!r})

    _val = _s.createText({bx} + {bw} * 0.55, _by, {bw} * 0.30, 4.5)
    _s.setText(_row["value"], _val)
    _s.setFontSize({float(value_font_size_pt)}, _val)
    _s.setTextColor({value_color!r}, _val)
    _s.setTextAlignment(2, _val)  # right

    _pct = _s.createText({bx} + {bw} * 0.85, _by, {bw} * 0.15, 4.5)
    _s.setText("%d %%" % int(round(_row["percent"])), _pct)
    _s.setFontSize({float(percent_font_size_pt)}, _pct)
    _s.setTextColor(_row["color"], _pct)
    _s.setTextAlignment(2, _pct)
    _try_set_font(_pct, {percent_font!r})

    # Track + fill (stacked rects)
    _track = _s.createRect({bx}, _by + {float(bar_offset_mm)}, {bw}, {float(bar_height_mm)})
    _s.setFillColor({bar_track_color!r}, _track)
    _s.setFillShade({int(bar_track_shade)}, _track)
    _s.setLineColor("None", _track)
    try:
        _s.setCornerRadius({bar_radius_pt}, _track)
    except Exception:
        pass

    _fill_w = {bw} * (_row["percent"] / 100.0)
    _fill = _s.createRect({bx}, _by + {float(bar_offset_mm)}, _fill_w, {float(bar_height_mm)})
    _s.setFillColor(_row["color"], _fill)
    _s.setLineColor("None", _fill)
    try:
        _s.setCornerRadius({bar_radius_pt}, _fill)
    except Exception:
        pass

    _rows.append({{
        "label": _label,
        "value": _val,
        "percent": _pct,
        "track": _track,
        "fill": _fill,
    }})

_value = {{
    "background": _bg,
    "title": _title,
    "headline": _headline,
    "caption": _caption,
    "rows": _rows,
}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "dark_kpi_band script failed"}

        out = res.value or {}
        return {
            "ok": True,
            "background": out.get("background"),
            "title": out.get("title"),
            "headline": out.get("headline"),
            "caption": out.get("caption"),
            "rows": out.get("rows", []),
            "bbox": {
                "x_mm": float(x_mm),
                "y_mm": float(y_mm),
                "width_mm": float(width_mm),
                "height_mm": float(height_mm),
            },
            "error": None,
        }

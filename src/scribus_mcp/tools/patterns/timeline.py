"""Horizontal timeline with circle markers, labels above, dates below.

Single-script-body design: the axis line, every marker, optional
connectors, all per-item labels and dates are computed Python-side and
emitted as one ``backend.script()`` call.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.patterns._styling import HAIRLINE_PT


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_timeline(
        items: list[dict],
        x_mm: float,
        width_mm: float,
        top_y_mm: float | None = None,
        axis_y_mm: float | None = None,
        axis_color: str = "Black",
        axis_shade: int = 50,
        axis_width_pt: float = 1.4,
        marker_color: str = "Black",
        marker_radius_mm: float = 1.6,
        marker_ring_color: str = "White",
        marker_ring_width_pt: float = 0.8,
        label_color: str = "Black",
        label_font_size_pt: float = 8.0,
        label_height_mm: float = 5.0,
        label_offset_mm: float = 5.0,
        date_color: str = "Black",
        date_font_size_pt: float = 7.0,
        date_shade: int = 55,
        date_offset_mm: float = 4.0,
        connector_color: str = "Black",
        connector_shade: int = 25,
        show_connectors: bool = True,
        mode: Mode = "auto",
    ) -> dict:
        """Horizontal timeline with circle markers, labels above, and dates below.

        ``items`` is a list of dicts. Each dict requires:
            - ``position``: number in [0, 1], horizontal position along the axis
            - ``label``: short caption (placed above the axis)
        Optional per item:
            - ``date``: short date string (placed below the axis)

        Vertical placement — pass exactly one:
          - ``top_y_mm``: y of the top of the timeline's full footprint
            (top of the labels above the axis). Best when you've
            allocated a band via PageCursor — pass ``slot["y_mm"]``
            directly and the labels stay inside.
          - ``axis_y_mm``: y of the axis line itself. Useful if you want
            the axis at a specific page anchor; labels render above and
            dates below.

        The axis is a thin horizontal line; each event is anchored by a
        filled circle marker (with a thin ring for separation against any
        background). Optional faint vertical connectors link the marker
        to the label area.

        Per-event slot width is computed from the bounding box, so labels
        are sized to not overlap their neighbours regardless of how many
        events you pack in.

        The result includes ``"bbox"`` — the true full footprint
        (labels above + axis + dates below) — so callers can stack the
        next band cleanly without guessing.
        """
        if not items:
            return {"ok": False, "error": "need at least one item"}
        for i, it in enumerate(items):
            if "position" not in it or "label" not in it:
                return {"ok": False, "error": f"item {i} missing 'position' or 'label'"}

        # Resolve vertical placement — exactly one of {top_y_mm, axis_y_mm}.
        if top_y_mm is None and axis_y_mm is None:
            return {
                "ok": False,
                "error": "must provide one of top_y_mm or axis_y_mm",
            }
        if top_y_mm is not None and axis_y_mm is not None:
            return {
                "ok": False,
                "error": "pass only one of top_y_mm or axis_y_mm, not both",
            }
        if top_y_mm is not None:
            axis_y = float(top_y_mm) + float(label_offset_mm) + float(label_height_mm)
        else:
            axis_y = float(axis_y_mm)
        # Internal alias used below — was named y_mm before the rename.
        y_mm = axis_y

        n = len(items)
        slot_w = max(20.0, (width_mm * 0.95) / max(1, n - 1)) if n > 1 else width_mm * 0.6
        label_w = min(40.0, slot_w * 0.95)

        # ---- Pre-compute every primitive's spec Python-side -------------

        # Connectors: list of (x1, y1, x2, y2)
        connectors_spec = []
        # Markers: list of (x, y, size, fill, line_color_or_None, line_w)
        markers_spec = []
        # Labels: list of (x, y, w, h, text)
        labels_spec = []
        # Dates: list of (x, y, w, h, text)
        dates_spec = []

        for it in items:
            pos = max(0.0, min(1.0, float(it["position"])))
            tx = x_mm + pos * width_mm

            if show_connectors:
                connectors_spec.append(
                    (tx, y_mm - marker_radius_mm, tx, y_mm - label_offset_mm + 0.5)
                )

            markers_spec.append(
                (
                    tx - marker_radius_mm,
                    y_mm - marker_radius_mm,
                    marker_radius_mm * 2,
                    marker_color,
                    marker_ring_color if marker_ring_color and marker_ring_color != "None" else None,
                    float(marker_ring_width_pt),
                )
            )

            label_y = y_mm - label_offset_mm - label_height_mm
            # Center the label on the marker, but clamp so it doesn't
            # extend past the timeline's horizontal span — otherwise the
            # first/last labels poke into the page margins.
            label_x = max(x_mm, min(tx - label_w / 2, x_mm + width_mm - label_w))
            labels_spec.append((label_x, label_y, label_w, float(label_height_mm), str(it["label"])))

            if it.get("date"):
                date_y = y_mm + date_offset_mm
                date_x = max(x_mm, min(tx - label_w / 2, x_mm + width_mm - label_w))
                dates_spec.append((date_x, date_y, label_w, 5.0, str(it["date"])))

        # ---- One script body that creates everything --------------------
        body = f"""
import scribus as _s

_axis = _s.createLine({x_mm}, {y_mm}, {x_mm + width_mm}, {y_mm})
_s.setLineColor({axis_color!r}, _axis)
_s.setLineShade({int(axis_shade)}, _axis)
_s.setLineWidth({float(axis_width_pt)}, _axis)
_s.setLineCap(32, _axis)

_connector_names = []
for _x1, _y1, _x2, _y2 in {connectors_spec!r}:
    _n = _s.createLine(_x1, _y1, _x2, _y2)
    _s.setLineColor({connector_color!r}, _n)
    _s.setLineShade({int(connector_shade)}, _n)
    _s.setLineWidth({HAIRLINE_PT}, _n)
    _connector_names.append(_n)

_marker_names = []
for _x, _y, _size, _fill, _ring, _ring_w in {markers_spec!r}:
    _n = _s.createEllipse(_x, _y, _size, _size)
    _s.setFillColor(_fill, _n)
    if _ring is not None:
        _s.setLineColor(_ring, _n)
        _s.setLineWidth(_ring_w, _n)
    else:
        _s.setLineColor("None", _n)
    _marker_names.append(_n)

_label_names = []
for _x, _y, _w, _h, _text in {labels_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(label_font_size_pt)}, _n)
    _s.setTextColor({label_color!r}, _n)
    _s.setTextAlignment(1, _n)
    _label_names.append(_n)

_date_names = []
for _x, _y, _w, _h, _text in {dates_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(date_font_size_pt)}, _n)
    _s.setTextColor({date_color!r}, _n)
    if {int(date_shade)} != 100:
        try:
            _s.setTextShade({int(date_shade)}, _n)
        except Exception:
            pass  # not all Scribus builds expose setTextShade
    _s.setTextAlignment(1, _n)
    _date_names.append(_n)

_value = {{
    "axis": _axis,
    "markers": _marker_names,
    "connectors": _connector_names,
    "labels": _label_names,
    "dates": _date_names,
}}
"""

        backend = await get_backend(ctx, mode)
        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "timeline script failed"}

        out = res.value or {}

        # Bbox of everything drawn: labels above the axis (height
        # label_offset + label_height), axis itself (negligible), dates
        # below (date_offset + 5 mm date frame).
        bbox_top = axis_y - label_offset_mm - label_height_mm
        bbox_bottom = axis_y + date_offset_mm + 5.0
        return {
            "ok": True,
            "axis": out.get("axis"),
            "markers": out.get("markers", []),
            "connectors": out.get("connectors", []),
            "labels": out.get("labels", []),
            "dates": out.get("dates", []),
            "bbox": {
                "x_mm": x_mm,
                "y_mm": bbox_top,
                "width_mm": width_mm,
                "height_mm": bbox_bottom - bbox_top,
            },
        }

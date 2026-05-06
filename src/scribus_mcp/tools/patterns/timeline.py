"""Horizontal timeline with circle markers, labels above, dates below.

Single-script-body design: the axis line, every marker, optional
connectors, all per-item labels and dates are computed Python-side and
emitted as one ``backend.script()`` call.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects
from scribus_mcp.tools.patterns._styling import HAIRLINE_PT


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_timeline(
        items: list[dict],
        x_mm: float,
        width_mm: float,
        top_y_mm: float | None = None,
        axis_y_mm: float | None = None,
        axis_color: str = "muted",
        axis_shade: int | None = None,
        axis_width_pt: float = 1.4,
        marker_color: str = "accent",
        marker_radius_mm: float = 1.6,
        marker_ring_color: str = "White",
        marker_ring_width_pt: float = 0.8,
        label_color: str = "ink",
        label_font_size_pt: float = 8.0,
        label_height_mm: float = 5.0,
        label_offset_mm: float = 5.0,
        label_rows: int | str = "auto",
        label_row_gap_mm: float = 2.0,
        date_color: str = "muted",
        date_font_size_pt: float = 7.0,
        date_shade: int | None = None,
        date_offset_mm: float = 4.0,
        connector_color: str = "muted",
        connector_shade: int | None = None,
        show_connectors: bool = True,
        bottom_margin_mm: float = 3.0,
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

        Per-event label width is bounded by the distance to each
        neighbour along the axis, so labels don't overlap even when the
        ``position`` values are unevenly spaced (e.g. yearly markers
        with a one-year gap next to a three-year gap).

        ``label_rows`` (default ``"auto"``) lets adjacent items
        alternate between N y-rows so each label competes only with the
        one ``label_rows`` items away — roughly ``label_rows×`` more
        horizontal slot per label. ``"auto"`` estimates each label's
        rendered width from its character count and the font size; if
        any label overflows its single-row slot, the timeline bumps to
        2 rows automatically. Pass an explicit integer (1..4) to
        override — e.g. ``label_rows=1`` to force a single line and
        accept the truncation, or ``label_rows=3`` for very dense
        timelines.

        With ``label_rows=1`` (single row), all labels sit above the
        axis and dates below — the classic timeline look. With
        ``label_rows>=2``, even rows (0, 2, ...) sit above the axis and
        odd rows (1, 3, ...) sit below, so adjacent items split across
        the axis line. In the multi-row case dates render close to the
        axis on the same side as their item's label (between label and
        axis); the label is pushed outward to leave room. Higher rings
        (e.g. row 2 above row 0) stack
        ``label_height_mm + label_row_gap_mm`` further out.

        ``bottom_margin_mm`` is visual breathing room added to the
        reported bbox below the date row — bumping it stops the next
        band (or the page footer) from sitting flush against the dates.

        The result includes ``"bbox"`` — the true full footprint
        (labels above + axis + dates below + bottom margin) — so callers
        can stack the next band cleanly without guessing.
        """
        if not items:
            return {"ok": False, "error": "need at least one item"}
        for i, it in enumerate(items):
            if "position" not in it or "label" not in it:
                return {"ok": False, "error": f"item {i} missing 'position' or 'label'"}

        # ``label_rows`` accepts an int (1..4) or the string ``"auto"``.
        # Auto-detect picks 1 row when every label fits its same-row
        # slot, else 2 (the typical "two-height" stagger). Callers can
        # still force more rows by passing an explicit int.
        positions = [max(0.0, min(1.0, float(it["position"]))) for it in items]

        def _est_label_width_mm(text: str) -> float:
            # 0.62 em per char matches the empirical advance for DejaVu
            # Sans Book — same factor the kpi_tile autofit lands on.
            # Capital-leading words like "Bluetooth" or "LTS v3.7" run
            # wider than the 0.55 average; underestimating means auto
            # leaves the timeline at 1 row when 2 rows are needed.
            return len(text) * 0.62 * float(label_font_size_pt) / 2.834645669

        def _slot_avail_mm(i: int, rows: int) -> float:
            row = i % rows
            left = float("inf")
            for j in range(i - 1, -1, -1):
                if j % rows == row:
                    left = (positions[i] - positions[j]) * float(width_mm)
                    break
            right = float("inf")
            for j in range(i + 1, len(positions)):
                if j % rows == row:
                    right = (positions[j] - positions[i]) * float(width_mm)
                    break
            avail = min(left, right)
            if avail == float("inf"):
                avail = float(width_mm) * 0.6
            return min(40.0, max(8.0, avail * 0.95))

        def _fits_at_rows(rows: int) -> bool:
            for i, it in enumerate(items):
                if _est_label_width_mm(str(it["label"])) > _slot_avail_mm(i, rows):
                    return False
            return True

        if isinstance(label_rows, str):
            stripped = label_rows.strip().lower()
            if stripped == "auto":
                label_rows = 1 if _fits_at_rows(1) else 2
            elif stripped.isdigit():
                label_rows = int(stripped)
                if not 1 <= label_rows <= 4:
                    return {"ok": False, "error": "label_rows must be between 1 and 4"}
            else:
                return {
                    "ok": False,
                    "error": (
                        f"label_rows must be an int 1..4 or the string 'auto' "
                        f"(got {label_rows!r})"
                    ),
                }
        else:
            if not 1 <= int(label_rows) <= 4:
                return {"ok": False, "error": "label_rows must be between 1 and 4"}
            label_rows = int(label_rows)

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
        # Multi-row mode (label_rows>=2) splits items above/below the
        # axis. Dates render on the same side as their item, close to
        # the axis (between label and axis), so the label has to sit
        # further out when any item carries a date.
        DATE_HEIGHT_MM = 5.0
        DATE_LABEL_GAP_MM = 1.0
        any_date = any(it.get("date") for it in items)
        if label_rows >= 2 and any_date:
            side_anchor = max(
                float(label_offset_mm),
                float(date_offset_mm) + DATE_HEIGHT_MM + DATE_LABEL_GAP_MM,
            )
        else:
            side_anchor = float(label_offset_mm)
        row_step = float(label_height_mm) + float(label_row_gap_mm)

        if label_rows == 1:
            # Backward-compat single-row: all labels above the axis,
            # dates below.
            max_above_ring = 0
            max_below_ring = -1
        else:
            max_above_ring = (label_rows - 1) // 2
            max_below_ring = (label_rows - 2) // 2

        # Distance from axis to the top of the highest above-row label.
        above_extent = (
            side_anchor
            + float(label_height_mm)
            + max_above_ring * row_step
        )
        if top_y_mm is not None:
            axis_y = float(top_y_mm) + above_extent
        else:
            axis_y = float(axis_y_mm)
        # Internal alias used below — was named y_mm before the rename.
        y_mm = axis_y

        backend = await get_backend(ctx, mode)
        axis_color, axis_shade = await resolve_color(
            backend, axis_color, fallback_shade=50, current_shade=axis_shade,
        )
        marker_color, _ = await resolve_color(backend, marker_color)
        label_color, _ = await resolve_color(backend, label_color)
        date_color, date_shade = await resolve_color(
            backend, date_color, fallback_shade=55, current_shade=date_shade,
        )
        connector_color, connector_shade = await resolve_color(
            backend, connector_color, fallback_shade=25, current_shade=connector_shade,
        )

        n = len(items)
        # Per-item label width — bounded by the distance to each
        # *same-row* neighbour along the axis. With evenly spaced items
        # and label_rows=1 this matches the previous uniform slot_w
        # behaviour. With label_rows=2, items 0,2,4 share row 0 (above)
        # and items 1,3,5 share row 1 (below), so each label only
        # competes with the label two markers away — roughly 2x more
        # horizontal slot.
        item_rows = [i % label_rows for i in range(n)]

        def _same_row_neighbour(i: int, direction: int) -> float:
            """Return horizontal distance (mm) to the nearest same-row
            neighbour in ``direction`` (-1=left, +1=right). Falls back
            to ``inf`` when no same-row neighbour exists on that side
            (i.e. the item is at a row's leading or trailing edge)."""
            row = item_rows[i]
            j = i + direction
            while 0 <= j < n:
                if item_rows[j] == row:
                    return abs(positions[j] - positions[i]) * width_mm
                j += direction
            return float("inf")

        label_widths: list[float] = []
        for i in range(n):
            left_dist = _same_row_neighbour(i, -1)
            right_dist = _same_row_neighbour(i, +1)
            avail = min(left_dist, right_dist)
            if avail == float("inf"):
                avail = width_mm * 0.6
            label_widths.append(min(40.0, max(8.0, avail * 0.95)))

        # ---- Pre-compute every primitive's spec Python-side -------------

        # Connectors: list of (x1, y1, x2, y2)
        connectors_spec = []
        # Markers: list of (x, y, size, fill, line_color_or_None, line_w)
        markers_spec = []
        # Labels: list of (x, y, w, h, text)
        labels_spec = []
        # Dates: list of (x, y, w, h, text)
        dates_spec = []

        # Per-row vertical placement.
        # ``label_rows == 1``: all rows above (legacy behaviour),
        #   label_y(0) = axis - label_offset - label_h.
        # ``label_rows >= 2``: even rows above, odd rows below; the
        #   ring index ``r // 2`` controls how far from the axis the
        #   row sits, with ring 0 closest. Dates ride along on the same
        #   side as the label, between the label and the axis.

        def _placement_for_row(row: int) -> tuple[int, float, float]:
            """Return (side, label_y, date_y) for a given item row.

            ``side`` is -1 (above) or +1 (below).
            """
            if label_rows == 1:
                label_y = y_mm - side_anchor - float(label_height_mm) - row * row_step
                date_y = y_mm + float(date_offset_mm)
                return -1, label_y, date_y
            ring = row // 2
            if row % 2 == 0:
                side = -1
                label_y = (
                    y_mm
                    - side_anchor
                    - float(label_height_mm)
                    - ring * row_step
                )
                date_y = y_mm - float(date_offset_mm) - DATE_HEIGHT_MM
            else:
                side = +1
                label_y = y_mm + side_anchor + ring * row_step
                date_y = y_mm + float(date_offset_mm)
            return side, label_y, date_y

        for idx, it in enumerate(items):
            pos = positions[idx]
            tx = x_mm + pos * width_mm
            label_w = label_widths[idx]
            row = item_rows[idx]
            side, label_y, date_y = _placement_for_row(row)

            if show_connectors:
                # Connector hugs the side of the marker pointing at the
                # label, reaching just inside the label frame.
                if side < 0:
                    connectors_spec.append(
                        (tx, y_mm - marker_radius_mm, tx, label_y + float(label_height_mm) - 0.5)
                    )
                else:
                    connectors_spec.append(
                        (tx, y_mm + marker_radius_mm, tx, label_y + 0.5)
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

            # Center the label on the marker, but clamp so it doesn't
            # extend past the timeline's horizontal span — otherwise the
            # first/last labels poke into the page margins.
            label_x = max(x_mm, min(tx - label_w / 2, x_mm + width_mm - label_w))
            labels_spec.append((label_x, label_y, label_w, float(label_height_mm), str(it["label"])))

            if it.get("date"):
                date_x = max(x_mm, min(tx - label_w / 2, x_mm + width_mm - label_w))
                dates_spec.append((date_x, date_y, label_w, DATE_HEIGHT_MM, str(it["date"])))

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

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "timeline script failed"}

        out = res.value or {}
        group_name = await group_created_objects(
            backend,
            [out.get("axis")]
            + list(out.get("connectors", []))
            + list(out.get("markers", []))
            + list(out.get("labels", []))
            + list(out.get("dates", [])),
        )

        # Bbox of everything drawn. The "above" side covers the label
        # stack reaching out to ring ``max_above_ring``; the "below"
        # side covers either the legacy date row (label_rows=1) or the
        # mirrored label stack (label_rows>=2). ``bottom_margin_mm`` is
        # visual breathing room so callers chaining via PageCursor
        # don't slam the next band into the timeline.
        bbox_top = axis_y - above_extent
        if label_rows == 1:
            bbox_bottom = (
                axis_y + float(date_offset_mm) + DATE_HEIGHT_MM + float(bottom_margin_mm)
            )
        else:
            below_extent = (
                side_anchor
                + float(label_height_mm)
                + max_below_ring * row_step
            )
            bbox_bottom = axis_y + below_extent + float(bottom_margin_mm)
        return {
            "ok": True,
            "axis": out.get("axis"),
            "markers": out.get("markers", []),
            "connectors": out.get("connectors", []),
            "labels": out.get("labels", []),
            "dates": out.get("dates", []),
            "group": group_name,
            # Surface the resolved row count so callers passing
            # ``label_rows="auto"`` can see whether single-row fit or
            # the timeline was bumped to two-row staggered.
            "label_rows": label_rows,
            "bbox": {
                "x_mm": x_mm,
                "y_mm": bbox_top,
                "width_mm": width_mm,
                "height_mm": bbox_bottom - bbox_top,
            },
        }

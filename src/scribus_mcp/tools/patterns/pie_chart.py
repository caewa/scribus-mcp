"""Pie chart approximated by polygon slices, with optional clean outer ring.

Single-script-body design (mirrors bar_chart): every slice polygon, the
optional outer ring, and the legend are computed Python-side and emitted
as one ``backend.script()`` call. Lets the pattern run in headless mode
with a single Scribus spawn instead of N+1.
"""

from __future__ import annotations

import math

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_pie_chart(
        labels: list[str],
        values: list[float],
        center_x_mm: float,
        center_y_mm: float,
        radius_mm: float = 30.0,
        colors: list[str] | None = None,
        outline_color: str = "None",
        outline_width_pt: float = 0.0,
        outer_ring_color: str = "",
        outer_ring_width_pt: float = 0.6,
        legend_position: str = "right",
        legend_label_width_mm: float = 32.0,
        show_legend: bool = True,
        label_font_size_pt: float = 8.0,
        label_color: str = "ink",
        mode: Mode = "auto",
    ) -> dict:
        """Pie chart approximated by polygons (one per slice). Each slice is a
        polygon with the center as one vertex and many points along its arc.

        Slice outlines default to none — drawing per-slice strokes creates a
        visible "wagon wheel" of spokes converging at the center because
        every slice's two radial edges overlap there. To get a clean outer
        boundary instead, set ``outer_ring_color`` (e.g. ``"White"``) and a
        plain circle will be drawn behind the slices.

        Legend placement (``legend_position``):
          - ``"right"`` (default): vertical column right of the pie. Each
            row is a swatch + ``"<label> — <pct>%"``. Label text width is
            ``legend_label_width_mm`` — shrink it if your slot is narrow,
            or switch to ``"below"`` if the pie is in a half-width column.
          - ``"below"``: horizontal row underneath the pie, centered on
            the pie's x. Useful when there's no horizontal slack to the
            right.
          - ``"none"``: no legend; ``show_legend=False`` is also honoured
            for backward compatibility.

        ``colors`` defaults to a CMYK rotation of Black, Cyan, Magenta, Yellow,
        Red, Blue, Green — colours must already be defined in the document.
        Use ``define_color_*`` to add custom slice colours first.
        """
        if legend_position not in ("right", "below", "none"):
            return {
                "ok": False,
                "error": f"legend_position must be 'right', 'below', or 'none' (got {legend_position!r})",
            }
        if len(labels) != len(values):
            return {"ok": False, "error": "labels and values must have the same length"}
        n = len(values)
        if n < 2:
            return {"ok": False, "error": "need at least 2 slices"}
        total = sum(values)
        if total <= 0:
            return {"ok": False, "error": "sum of values must be > 0"}

        backend = await get_backend(ctx, mode)
        label_color, _ = await resolve_color(backend, label_color)

        default_colors = ["Black", "Cyan", "Magenta", "Yellow", "Red", "Blue", "Green"]
        slice_colors = list(colors) if colors else default_colors
        while len(slice_colors) < n:
            slice_colors += default_colors

        # ---- Pre-compute every primitive's spec Python-side -------------

        # Outer ring (optional): one ellipse drawn first, behind slices.
        outer_ring_spec: dict | None = None
        if outer_ring_color:
            outer_ring_spec = {
                "x": center_x_mm - radius_mm,
                "y": center_y_mm - radius_mm,
                "size": radius_mm * 2,
            }

        # Slices: list of (flat_points, fill_color, line_color, line_width_pt)
        slices_spec = []
        steps_per_slice = 24  # arc-approximation density
        cum_angle = -math.pi / 2  # start at 12 o'clock
        for i, v in enumerate(values):
            slice_angle = (v / total) * 2 * math.pi
            steps = max(2, int(steps_per_slice * (slice_angle / (2 * math.pi)) * n))
            pts = [(center_x_mm, center_y_mm)]
            for s in range(steps + 1):
                a = cum_angle + slice_angle * (s / steps)
                pts.append(
                    (center_x_mm + radius_mm * math.cos(a), center_y_mm + radius_mm * math.sin(a))
                )
            flat = [c for pt in pts for c in pt]
            slices_spec.append(
                (
                    list(flat),  # createPolygon needs a Python list, not tuple
                    slice_colors[i],
                    outline_color,
                    float(outline_width_pt),
                )
            )
            cum_angle += slice_angle

        # Legend
        legend_swatches_spec = []  # list of (x, y, w, h, fill_color)
        legend_texts_spec = []  # list of (x, y, w, h, text)
        effective_pos = "none" if not show_legend else legend_position
        if effective_pos == "right":
            row_h = 6.0
            legend_x = center_x_mm + radius_mm + 6
            legend_y_start = center_y_mm - (n * row_h) / 2
            for i, lab in enumerate(labels):
                row_y = legend_y_start + i * row_h
                legend_swatches_spec.append((legend_x, row_y, 4.0, 4.0, slice_colors[i]))
                pct = 100 * values[i] / total
                legend_texts_spec.append(
                    (
                        legend_x + 5,
                        row_y,
                        legend_label_width_mm,
                        5.0,
                        f"{lab} — {pct:.1f}%",
                    )
                )
        elif effective_pos == "below":
            sw_size = 3.0
            gap_inner = 1.0
            inter_item = 4.0
            item_w = sw_size + gap_inner + legend_label_width_mm
            row_w = item_w * n + inter_item * (n - 1)
            row_x = center_x_mm - row_w / 2
            row_y = center_y_mm + radius_mm + 4
            for i, lab in enumerate(labels):
                base_x = row_x + i * (item_w + inter_item)
                legend_swatches_spec.append(
                    (base_x, row_y + 0.5, sw_size, sw_size, slice_colors[i])
                )
                pct = 100 * values[i] / total
                legend_texts_spec.append(
                    (
                        base_x + sw_size + gap_inner,
                        row_y,
                        legend_label_width_mm,
                        5.0,
                        f"{lab} — {pct:.1f}%",
                    )
                )

        # Decode any HTML entities the LLM may have pre-encoded in labels.
        legend_texts_spec = [
            (x, y, w, h, clean_user_text(t)) for x, y, w, h, t in legend_texts_spec
        ]

        # ---- One script body that creates everything --------------------
        body = f"""
import scribus as _s

_outer_ring = None
_outer_ring_spec = {outer_ring_spec!r}
if _outer_ring_spec:
    _outer_ring = _s.createEllipse(
        _outer_ring_spec["x"], _outer_ring_spec["y"],
        _outer_ring_spec["size"], _outer_ring_spec["size"],
    )
    _s.setFillColor("None", _outer_ring)
    _s.setLineColor({outer_ring_color!r}, _outer_ring)
    _s.setLineWidth({float(outer_ring_width_pt)}, _outer_ring)

_slice_names = []
for _flat, _fill, _line, _line_w in {slices_spec!r}:
    _n = _s.createPolygon(_flat)
    _s.setFillColor(_fill, _n)
    _s.setLineColor(_line, _n)
    if _line != "None":
        _s.setLineWidth(_line_w, _n)
    _slice_names.append(_n)

_legend_names = []
for _x, _y, _w, _h, _fill in {legend_swatches_spec!r}:
    _n = _s.createRect(_x, _y, _w, _h)
    _s.setFillColor(_fill, _n)
    _s.setLineColor("None", _n)
    _legend_names.append(_n)
for _x, _y, _w, _h, _text in {legend_texts_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(label_font_size_pt)}, _n)
    _s.setTextColor({label_color!r}, _n)
    _legend_names.append(_n)

_value = {{
    "outer_ring": _outer_ring,
    "slices": _slice_names,
    "legend": _legend_names,
}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "pie_chart script failed"}

        out = res.value or {}
        group_name = await group_created_objects(
            backend,
            list(out.get("slices", []))
            + list(out.get("legend", []))
            + [out.get("outer_ring")],
        )
        return {
            "ok": True,
            "slices": out.get("slices", []),
            "legend": out.get("legend", []),
            "outer_ring": out.get("outer_ring"),
            "group": group_name,
            "error": None,
        }

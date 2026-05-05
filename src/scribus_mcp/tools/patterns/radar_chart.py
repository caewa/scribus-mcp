"""Radar / spider / "compétences" chart.

Single-dataset (legacy): pass ``values=[…]`` for one polygon overlay.

Multi-dataset (compare variants): pass ``datasets=[{…}, {…}]`` and each
entry produces its own polygon. Each dataset can carry its own colors;
the tool stacks them with partial transparency so overlaps stay legible
and renders an optional legend below the chart.

Single-script-body design: every ring polygon, axis line, data overlay,
axis label, and legend item is computed Python-side and dispatched as
one ``backend.script()`` call — keeps headless mode usable.
"""

from __future__ import annotations

import math

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._styling import THIN_PT


def _radar_geometry(
    cx: float,
    cy: float,
    radius: float,
    n: int,
) -> list[tuple[float, float]]:
    """Return n points on a circle around (cx, cy), starting at the top
    (12 o'clock) and going clockwise."""
    pts = []
    for i in range(n):
        angle = -math.pi / 2 + (2 * math.pi * i) / n
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return pts


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_radar_chart(
        axes: list[str],
        center_x_mm: float,
        center_y_mm: float,
        values: list[float] | None = None,
        datasets: list[dict] | None = None,
        radius_mm: float = 50.0,
        max_value: float = 1.0,
        rings: int = 4,
        ring_color: str = "muted",
        ring_shade: int | None = None,
        axis_color: str = "muted",
        axis_shade: int | None = None,
        data_fill_color: str = "accent",
        data_fill_shade: int | None = None,
        data_line_color: str = "accent",
        data_line_width_pt: float = 1.5,
        data_fill_alpha: float = 1.0,
        label_font_size_pt: float = 8.0,
        label_color: str = "ink",
        label_offset_mm: float = 4.0,
        label_width_mm: float = 22.0,
        label_height_mm: float = 5.0,
        legend_position: str = "below",
        legend_font_size_pt: float = 7.5,
        legend_swatch_mm: float = 3.0,
        legend_gap_mm: float = 4.0,
        mode: Mode = "auto",
    ) -> dict:
        """Create a radar / spider / "compétences" chart in one call.

        Layout: ``len(axes)`` axes radiating from (center_x, center_y),
        each ``radius`` mm long. Concentric "rings" form the background
        grid.

        **Single dataset (legacy)**: pass ``values=[…]`` (one float per
        axis, 0…``max_value``). The fill / line colors come from
        ``data_fill_color`` / ``data_line_color``.

        **Multiple datasets (compare variants)**: pass ``datasets`` —
        a list of dicts, each with:

            {
              "label":         "Q1",                # for the legend
              "values":        [0.8, 0.6, 0.9, …],  # one per axis
              "fill_color":    "Brand Deep",        # optional override
              "fill_shade":    22,                  # optional
              "fill_alpha":    0.5,                 # opacity 0–1, default 0.5
              "line_color":    "Brand Deep",        # optional
              "line_width_pt": 1.4,                 # optional
            }

        Multi-dataset polygons render with partial transparency
        (``fill_alpha`` defaults to 0.5) so overlaps remain readable.

        Optional legend below the chart (``legend_position="below"``,
        the default; pass ``"none"`` to suppress). Items are spread
        horizontally and centered on the chart's x.

        All colors must already be defined in the document. Use
        ``define_color_cmyk`` or ``define_color_rgb`` first if needed.

        **Sizing the surrounding slot**: the chart's labels extend
        beyond the rings by roughly
        ``label_offset_mm + label_width_mm/2`` on every side, plus the
        legend (~10 mm) below if enabled. Defaults keep the chart tight
        enough to fit a half-width column.
        """
        # ---- Validate inputs ------------------------------------------------
        n = len(axes)
        if n < 3:
            return {"ok": False, "error": "need at least 3 axes for a radar chart"}
        if max_value <= 0:
            return {"ok": False, "error": "max_value must be > 0"}
        if rings < 1:
            return {"ok": False, "error": "rings must be >= 1"}

        if datasets is None and values is None:
            return {
                "ok": False,
                "error": "must provide either values=[...] (single dataset) or datasets=[...] (multi)",
            }
        if datasets is not None and values is not None:
            return {
                "ok": False,
                "error": "pass either values OR datasets, not both",
            }
        if values is not None and len(values) != n:
            return {
                "ok": False,
                "error": f"axes ({n}) and values ({len(values)}) must have the same length",
            }

        backend = await get_backend(ctx, mode)
        ring_color, ring_shade = await resolve_color(
            backend, ring_color, fallback_shade=20, current_shade=ring_shade,
        )
        axis_color, axis_shade = await resolve_color(
            backend, axis_color, fallback_shade=35, current_shade=axis_shade,
        )
        data_fill_color, data_fill_shade = await resolve_color(
            backend, data_fill_color, fallback_shade=25, current_shade=data_fill_shade,
        )
        data_line_color, _ = await resolve_color(backend, data_line_color)
        label_color, _ = await resolve_color(backend, label_color)

        if datasets is None:
            datasets = [
                {
                    "label": "",
                    "values": values,
                    "fill_color": data_fill_color,
                    "fill_shade": data_fill_shade,
                    "line_color": data_line_color,
                    "line_width_pt": data_line_width_pt,
                    "fill_alpha": data_fill_alpha,
                }
            ]
            multi = False
        else:
            multi = True

        for i, ds in enumerate(datasets):
            ds_values = ds.get("values")
            if ds_values is None or len(ds_values) != n:
                return {
                    "ok": False,
                    "error": (
                        f"dataset {i} ({ds.get('label', '')!r}) must carry values "
                        f"of length {n} (got {len(ds_values) if ds_values else 'None'})"
                    ),
                }

        if legend_position not in ("below", "none"):
            return {
                "ok": False,
                "error": f"legend_position must be 'below' or 'none' (got {legend_position!r})",
            }

        # ---- Pre-compute every primitive's spec Python-side -------------

        # Rings: list of flat-points lists (one per ring polygon)
        rings_spec = []
        for r_idx in range(1, rings + 1):
            r = radius_mm * (r_idx / rings)
            pts = _radar_geometry(center_x_mm, center_y_mm, r, n)
            rings_spec.append([c for pt in pts for c in pt])

        # Axes: list of (x1, y1, x2, y2)
        outer_pts = _radar_geometry(center_x_mm, center_y_mm, radius_mm, n)
        axes_spec = [(center_x_mm, center_y_mm, ox, oy) for ox, oy in outer_pts]

        # Data overlays — list of dicts (carry per-dataset styling).
        default_alpha = 0.5 if multi else 1.0
        data_spec = []
        for ds in datasets:
            ds_values = ds["values"]
            data_pts = []
            for i, v in enumerate(ds_values):
                v_clamped = max(0.0, min(float(v), float(max_value)))
                r = radius_mm * (v_clamped / max_value)
                angle = -math.pi / 2 + (2 * math.pi * i) / n
                data_pts.append(
                    (center_x_mm + r * math.cos(angle), center_y_mm + r * math.sin(angle))
                )
            data_spec.append(
                (
                    [c for pt in data_pts for c in pt],
                    ds.get("fill_color", data_fill_color),
                    int(ds.get("fill_shade", data_fill_shade)),
                    ds.get("line_color", data_line_color),
                    float(ds.get("line_width_pt", data_line_width_pt)),
                    float(ds.get("fill_alpha", default_alpha)),
                )
            )

        # Axis labels: list of (x, y, w, h, text)
        labels_spec = []
        for i, axis_label in enumerate(axes):
            angle = -math.pi / 2 + (2 * math.pi * i) / n
            lx = center_x_mm + (radius_mm + label_offset_mm) * math.cos(angle)
            ly = center_y_mm + (radius_mm + label_offset_mm) * math.sin(angle)
            labels_spec.append(
                (
                    lx - label_width_mm / 2,
                    ly - label_height_mm / 2,
                    float(label_width_mm),
                    float(label_height_mm),
                    str(axis_label),
                )
            )

        # Legend (optional, only on multi-dataset + below)
        legend_swatches_spec = []
        legend_texts_spec = []
        show_legend = multi and legend_position == "below"
        if show_legend:
            item_text_w = 22.0
            item_height = max(legend_swatch_mm, legend_font_size_pt * 0.45)
            item_gap = 1.0
            inter_item_gap = legend_gap_mm
            item_w = legend_swatch_mm + item_gap + item_text_w
            row_w = item_w * len(datasets) + inter_item_gap * (len(datasets) - 1)
            legend_y = (
                center_y_mm
                + radius_mm
                + label_offset_mm
                + label_height_mm / 2
                + 4.0
            )
            row_x = center_x_mm - row_w / 2
            for ds_idx, ds in enumerate(datasets):
                base_x = row_x + ds_idx * (item_w + inter_item_gap)
                sw_y = legend_y + (item_height - legend_swatch_mm) / 2
                legend_swatches_spec.append(
                    (
                        base_x,
                        sw_y,
                        legend_swatch_mm,
                        legend_swatch_mm,
                        ds.get("fill_color", data_fill_color),
                        int(ds.get("fill_shade", data_fill_shade)),
                    )
                )
                legend_texts_spec.append(
                    (
                        base_x + legend_swatch_mm + item_gap,
                        legend_y,
                        item_text_w,
                        item_height + 1.0,
                        str(ds.get("label", "")),
                    )
                )

        # Decode any HTML entities the LLM may have pre-encoded in labels.
        labels_spec = [
            (x, y, w, h, clean_user_text(t)) for x, y, w, h, t in labels_spec
        ]
        legend_texts_spec = [
            (x, y, w, h, clean_user_text(t)) for x, y, w, h, t in legend_texts_spec
        ]

        # ---- One script body that creates everything --------------------
        body = f"""
import scribus as _s

_ring_names = []
for _flat in {rings_spec!r}:
    _n = _s.createPolygon(_flat)
    _s.setFillColor("None", _n)
    _s.setLineColor({ring_color!r}, _n)
    _s.setLineShade({int(ring_shade)}, _n)
    _s.setLineWidth({THIN_PT}, _n)
    _ring_names.append(_n)

_axis_names = []
for _x1, _y1, _x2, _y2 in {axes_spec!r}:
    _n = _s.createLine(_x1, _y1, _x2, _y2)
    _s.setLineColor({axis_color!r}, _n)
    _s.setLineShade({int(axis_shade)}, _n)
    _s.setLineWidth({THIN_PT}, _n)
    _axis_names.append(_n)

_data_names = []
for _flat, _fill, _fshade, _line, _lw, _alpha in {data_spec!r}:
    _n = _s.createPolygon(_flat)
    _s.setFillColor(_fill, _n)
    _s.setFillShade(_fshade, _n)
    _s.setLineColor(_line, _n)
    _s.setLineWidth(_lw, _n)
    if 0.0 <= _alpha < 1.0:
        _s.setFillTransparency(_alpha, _n)
    _data_names.append(_n)

_label_names = []
for _x, _y, _w, _h, _text in {labels_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(label_font_size_pt)}, _n)
    _s.setTextColor({label_color!r}, _n)
    _s.setTextAlignment(1, _n)
    _label_names.append(_n)

_legend_names = []
for _x, _y, _w, _h, _fill, _fshade in {legend_swatches_spec!r}:
    _n = _s.createRect(_x, _y, _w, _h)
    _s.setFillColor(_fill, _n)
    _s.setFillShade(_fshade, _n)
    _s.setLineColor("None", _n)
    _legend_names.append(_n)
for _x, _y, _w, _h, _text in {legend_texts_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(legend_font_size_pt)}, _n)
    _s.setTextColor({label_color!r}, _n)
    _legend_names.append(_n)

_value = {{
    "rings": _ring_names,
    "axes": _axis_names,
    "data": _data_names,
    "labels": _label_names,
    "legend": _legend_names,
}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "radar_chart script failed"}

        out = res.value or {}
        data_names = out.get("data", [])

        # Bbox math (mirrors previous behaviour).
        halo_x = label_offset_mm + label_width_mm / 2
        halo_y_top = label_offset_mm + label_height_mm / 2
        halo_y_bottom = halo_y_top
        if show_legend:
            halo_y_bottom += 4.0 + max(legend_swatch_mm, legend_font_size_pt * 0.45) + 1.0

        bbox_x = center_x_mm - radius_mm - halo_x
        bbox_y = center_y_mm - radius_mm - halo_y_top
        bbox_w = 2 * (radius_mm + halo_x)
        bbox_h = radius_mm + halo_y_top + radius_mm + halo_y_bottom

        return {
            "ok": True,
            # Backwards compat: keep ``data_polygon`` (singular) for the
            # single-dataset case so existing callers don't break.
            "data_polygon": data_names[0] if not multi and data_names else None,
            "data_polygons": data_names,
            "rings": out.get("rings", []),
            "axes": out.get("axes", []),
            "labels": out.get("labels", []),
            "legend": out.get("legend", []),
            "n_axes": n,
            "n_datasets": len(datasets),
            "bbox": {
                "x_mm": bbox_x,
                "y_mm": bbox_y,
                "width_mm": bbox_w,
                "height_mm": bbox_h,
            },
        }

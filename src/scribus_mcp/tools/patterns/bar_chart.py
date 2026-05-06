"""Vertical bar chart with gridlines and labels.

Single-dataset (legacy): pass ``values=[…]`` for plain bars.

Multi-dataset (compare variants): pass ``datasets=[{…}, {…}]`` and each
label position gets ``len(datasets)`` adjacent thin bars (a *grouped*
bar chart), color-coded per dataset, with an optional legend below.

**Implementation note**: this pattern emits *one* ``backend.script()``
call that creates every primitive (gridlines + bars + labels + legend)
in a single Scribus pass. That keeps headless mode usable — the
previous one-``backend.call()``-per-primitive design fired ~80 spawns
per chart in headless, which made the documented headless story
unusable.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects
from scribus_mcp.tools.patterns._styling import HAIRLINE_PT


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_bar_chart(
        labels: list[str],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        values: list[float] | None = None,
        datasets: list[dict] | None = None,
        max_value: float = 0.0,
        bar_color: str = "accent",
        bar_shade: int | None = None,
        gridlines: int = 4,
        gridline_color: str = "muted",
        gridline_shade: int | None = None,
        label_color: str = "ink",
        label_font_size_pt: float = 8.0,
        show_values: bool = False,
        legend_position: str = "below",
        legend_font_size_pt: float = 7.5,
        legend_swatch_mm: float = 3.0,
        legend_gap_mm: float = 4.0,
        legend_height_mm: float = 6.0,
        mode: Mode = "auto",
    ) -> dict:
        """Vertical bar chart inside the bounding box (x, y, width, height).

        **Single dataset (legacy)**: pass ``values=[…]`` (one float per
        label). Bars use ``bar_color`` / ``bar_shade``.

        **Multiple datasets (grouped bars)**: pass ``datasets`` — a list
        of dicts:

            {
              "label":      "Q1",                # for the legend
              "values":     [120, 180, 95, 245], # one per category
              "fill_color": "Brand Deep",        # optional override
              "fill_shade": 80,                  # optional
              "line_color": "None",              # optional
            }

        Each category position gets ``len(datasets)`` thin bars side by
        side. A small legend renders below the category labels by default
        (``legend_position="below"``; pass ``"none"`` to suppress).
        ``height_mm`` then includes the legend strip — so the bars
        themselves get ``height_mm - legend_height_mm`` of vertical space
        when a legend is shown.

        ``max_value=0`` (default) auto-scales to the largest value across
        all datasets. ``show_values`` writes each value above its bar
        (gets cramped fast with many datasets — disabled by default).

        **height_mm is inclusive** of every element the chart draws —
        bars, gridlines, the bottom category-label strip, and the legend
        strip when datasets are passed. So a slot of height 50 mm receives
        a chart whose total visual footprint is exactly 50 mm; you don't
        need to add a buffer for labels. The exact bbox is also returned
        in the result as ``"bbox": {"x_mm", "y_mm", "width_mm", "height_mm"}``.
        """
        if len(labels) < 1:
            return {"ok": False, "error": "need at least one label"}
        n = len(labels)

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
        if legend_position not in ("below", "none"):
            return {
                "ok": False,
                "error": f"legend_position must be 'below' or 'none' (got {legend_position!r})",
            }

        # Legacy single-dataset early check — preserves the historical
        # "labels and values must have the same length" error.
        if values is not None and len(values) != n:
            return {
                "ok": False,
                "error": "labels and values must have the same length",
            }

        backend = await get_backend(ctx, mode)
        bar_color, bar_shade = await resolve_color(
            backend, bar_color, fallback_shade=80, current_shade=bar_shade,
        )
        gridline_color, gridline_shade = await resolve_color(
            backend, gridline_color, fallback_shade=15, current_shade=gridline_shade,
        )
        label_color, _ = await resolve_color(backend, label_color)

        # Normalize the legacy single-dataset form into a datasets list.
        if datasets is None:
            datasets = [
                {
                    "label": "",
                    "values": values,
                    "fill_color": bar_color,
                    "fill_shade": bar_shade,
                    "line_color": "None",
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

        # Auto-scale across every dataset.
        if max_value <= 0:
            max_value = max(
                (max(ds["values"]) for ds in datasets if ds["values"]),
                default=1.0,
            )
        if max_value <= 0:
            max_value = 1.0

        # height_mm is inclusive: reserve strips at the bottom for the
        # category labels (always) and the legend (if multi-dataset),
        # plus a top strip for value labels (if show_values), then carve
        # out the remainder for bars + gridlines.
        bottom_label_strip_mm = 6.0  # 5 mm label height + 1 mm gap
        show_legend = multi and legend_position == "below"
        legend_strip_mm = legend_height_mm if show_legend else 0.0
        # Value labels render 5 mm above the bar top (4 mm tall frame +
        # 1 mm breathing) so we need a 6 mm cushion above the plot area.
        top_value_strip_mm = 6.0 if show_values else 0.0
        plot_h = height_mm - bottom_label_strip_mm - legend_strip_mm - top_value_strip_mm
        if plot_h <= 0:
            return {
                "ok": False,
                "error": (
                    "height_mm too small — must be greater than "
                    f"{bottom_label_strip_mm + legend_strip_mm + top_value_strip_mm} mm "
                    "(bottom labels + legend + top value strip)"
                ),
            }
        plot_top_y = y_mm + top_value_strip_mm

        # ---- Pre-compute every primitive's spec Python-side -------------
        # (server runs this; the script body below just iterates the lists
        # and asks Scribus to create + style each one in a single pass).

        # Gridlines: list of (x1, y1, x2, y2)
        gridlines_spec = []
        for i in range(1, gridlines + 1):
            gy = plot_top_y + plot_h - (plot_h * i / gridlines)
            gridlines_spec.append((x_mm, gy, x_mm + width_mm, gy))

        slots = compute_column_bboxes(x_mm, plot_top_y, width_mm, plot_h, n, 0)
        gap_ratio = 0.25  # 25% gap between category groups
        slot_w = slots[0]["width_mm"]
        group_w = slot_w * (1 - gap_ratio)
        group_off = (slot_w - group_w) / 2
        baseline = plot_top_y + plot_h

        n_ds = len(datasets)
        inter_gap_ratio = 0.08
        if n_ds == 1:
            sub_bar_w = group_w
            sub_gap = 0.0
        else:
            sub_gap = group_w * inter_gap_ratio / (n_ds - 1)
            sub_bar_w = (group_w - sub_gap * (n_ds - 1)) / n_ds

        # Bars: list of (x, y, w, h, fill_color, fill_shade, line_color)
        bars_spec = []
        # Value labels: list of (x, y, w, h, text)
        value_labels_spec = []
        # Category labels: list of (x, y, w, h, text)
        cat_labels_spec = []

        for i in range(n):
            for ds_idx, ds in enumerate(datasets):
                v = ds["values"][i]
                v_clamped = max(0.0, min(float(v), float(max_value)))
                bh = (v_clamped / max_value) * plot_h
                bx = slots[i]["x_mm"] + group_off + ds_idx * (sub_bar_w + sub_gap)
                by = baseline - bh
                bars_spec.append(
                    (
                        bx,
                        by,
                        sub_bar_w,
                        bh,
                        ds.get("fill_color", bar_color),
                        int(ds.get("fill_shade", bar_shade)),
                        ds.get("line_color", "None"),
                    )
                )
                if show_values:
                    value_labels_spec.append((bx, by - 5, sub_bar_w, 4.0, str(v)))
            cat_labels_spec.append(
                (slots[i]["x_mm"], baseline + 1, slot_w, 5.0, labels[i])
            )

        # Legend swatches + labels
        legend_swatches_spec = []
        legend_texts_spec = []
        if show_legend:
            item_text_w = 22.0
            item_height = max(legend_swatch_mm, legend_font_size_pt * 0.45)
            item_gap = 1.0
            inter_item_gap = legend_gap_mm
            item_w = legend_swatch_mm + item_gap + item_text_w
            row_w = item_w * n_ds + inter_item_gap * (n_ds - 1)
            row_x = x_mm + (width_mm - row_w) / 2
            legend_y = baseline + 1 + 5 + 1.5
            for ds_idx, ds in enumerate(datasets):
                base_x = row_x + ds_idx * (item_w + inter_item_gap)
                sw_y = legend_y + (item_height - legend_swatch_mm) / 2
                legend_swatches_spec.append(
                    (
                        base_x,
                        sw_y,
                        legend_swatch_mm,
                        legend_swatch_mm,
                        ds.get("fill_color", bar_color),
                        int(ds.get("fill_shade", bar_shade)),
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
        value_labels_spec = [
            (x, y, w, h, clean_user_text(t)) for x, y, w, h, t in value_labels_spec
        ]
        cat_labels_spec = [
            (x, y, w, h, clean_user_text(t)) for x, y, w, h, t in cat_labels_spec
        ]
        legend_texts_spec = [
            (x, y, w, h, clean_user_text(t)) for x, y, w, h, t in legend_texts_spec
        ]

        # ---- One script body that creates everything --------------------
        body = f"""
import scribus as _s

_gridline_names = []
for _x1, _y1, _x2, _y2 in {gridlines_spec!r}:
    _n = _s.createLine(_x1, _y1, _x2, _y2)
    _s.setLineColor({gridline_color!r}, _n)
    _s.setLineShade({int(gridline_shade)}, _n)
    _s.setLineWidth({HAIRLINE_PT}, _n)
    _gridline_names.append(_n)

_bar_names = []
for _x, _y, _w, _h, _fill, _shade, _line in {bars_spec!r}:
    _n = _s.createRect(_x, _y, _w, _h)
    _s.setFillColor(_fill, _n)
    _s.setFillShade(_shade, _n)
    _s.setLineColor(_line, _n)
    _bar_names.append(_n)

_value_label_names = []
for _x, _y, _w, _h, _text in {value_labels_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(label_font_size_pt)}, _n)
    _s.setTextColor({label_color!r}, _n)
    _s.setTextAlignment(1, _n)
    _value_label_names.append(_n)

_label_names = []
for _x, _y, _w, _h, _text in {cat_labels_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(label_font_size_pt)}, _n)
    _s.setTextColor({label_color!r}, _n)
    _s.setTextAlignment(1, _n)
    _label_names.append(_n)

_legend_names = []
for _x, _y, _w, _h, _fill, _shade in {legend_swatches_spec!r}:
    _n = _s.createRect(_x, _y, _w, _h)
    _s.setFillColor(_fill, _n)
    _s.setFillShade(_shade, _n)
    _s.setLineColor("None", _n)
    _legend_names.append(_n)
for _x, _y, _w, _h, _text in {legend_texts_spec!r}:
    _n = _s.createText(_x, _y, _w, _h)
    _s.setText(_text, _n)
    _s.setFontSize({float(legend_font_size_pt)}, _n)
    _s.setTextColor({label_color!r}, _n)
    _legend_names.append(_n)

_value = {{
    "bars": _bar_names,
    "gridlines": _gridline_names,
    "labels": _label_names,
    "value_labels": _value_label_names,
    "legend": _legend_names,
}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "bar_chart script failed"}

        out = res.value or {}
        group_name = await group_created_objects(
            backend,
            list(out.get("bars", []))
            + list(out.get("gridlines", []))
            + list(out.get("labels", []))
            + list(out.get("value_labels", []))
            + list(out.get("legend", [])),
        )
        return {
            "ok": True,
            "bars": out.get("bars", []),
            "gridlines": out.get("gridlines", []),
            "labels": out.get("labels", []),
            "value_labels": out.get("value_labels", []),
            "legend": out.get("legend", []),
            "group": group_name,
            "n_datasets": n_ds,
            # Ground-truth bbox of everything we drew — same numbers the
            # caller passed in, since height_mm is now inclusive.
            "bbox": {
                "x_mm": x_mm,
                "y_mm": y_mm,
                "width_mm": width_mm,
                "height_mm": height_mm,
            },
        }

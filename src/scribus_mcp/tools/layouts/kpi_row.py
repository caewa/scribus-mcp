"""Horizontal row of KPI tiles — KPI-specific consumer of the generic
``create_equal_columns`` primitive.

The column-splitting math lives in ``layouts.equal_columns``;
``create_kpi_row`` is the thin convenience layer that pairs that math
with the KPI-tile renderer. All tiles in the row are batched into ONE
``backend.script()`` call thanks to ``render_kpi_tile_script``.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.layouts._geometry import compute_column_bboxes
from scribus_mcp.tools.patterns.kpi_tile import render_kpi_tile_script


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_kpi_row(
        items: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 38.0,
        gap_mm: float = 3.0,
        # Default styling for tiles — overridable per-item via the item dict.
        fill_color: str = "Black",
        fill_shade: int = 12,
        value_color: str = "Black",
        value_font_size_pt: float = 22,
        label_color: str = "Black",
        label_font_size_pt: float = 8,
        delta_color: str = "Black",
        delta_font_size_pt: float = 8,
        compact: bool = False,
        mode: Mode = "auto",
    ) -> dict:
        """Render N KPI tiles in a horizontal row, evenly distributed across
        ``width_mm`` with ``gap_mm`` between tiles. The per-tile width is
        computed automatically so the row never overflows the bounding box.

        ``items`` is a list of dicts with keys:
            value: str (required)
            label: str (required)
            delta: str (optional)
            fill_color, fill_shade, value_color, label_color, delta_color: optional
                per-tile overrides of the row-level defaults

        Each tile's value font auto-shrinks (per ``create_kpi_tile``) if the
        requested ``value_font_size_pt`` doesn't fit the chosen height.

        ``compact=True`` propagates compact mode to every tile (halves
        padding + gaps). Pair with a smaller ``height_mm`` (e.g. 22 mm)
        and smaller ``value_font_size_pt`` (e.g. 18) for a dense row.
        """
        if not items:
            return {"ok": False, "error": "items must not be empty"}
        for i, it in enumerate(items):
            if "value" not in it or "label" not in it:
                return {"ok": False, "error": f"item {i} needs 'value' and 'label'"}

        bboxes = compute_column_bboxes(x_mm, y_mm, width_mm, height_mm, len(items), gap_mm)
        if not bboxes:
            return {
                "ok": False,
                "error": f"width_mm ({width_mm}) too small for {len(items)} tiles with gap {gap_mm}",
            }

        # Build one big script body: one fragment per tile, all dispatched
        # in a single backend.script() round-trip.
        fragments: list[str] = []
        per_tile_meta: list[dict] = []
        for i, (it, b) in enumerate(zip(items, bboxes, strict=False)):
            requested_value_font = it.get("value_font_size_pt", value_font_size_pt)
            fragment, used_font = render_kpi_tile_script(
                var_prefix=f"t{i}",
                value=it["value"],
                label=it["label"],
                delta=it.get("delta", ""),
                x_mm=b["x_mm"],
                y_mm=b["y_mm"],
                width_mm=b["width_mm"],
                height_mm=b["height_mm"],
                fill_color=it.get("fill_color", fill_color),
                fill_shade=it.get("fill_shade", fill_shade),
                value_color=it.get("value_color", value_color),
                value_font_size_pt=requested_value_font,
                label_color=it.get("label_color", label_color),
                label_font_size_pt=it.get("label_font_size_pt", label_font_size_pt),
                delta_color=it.get("delta_color", delta_color),
                delta_font_size_pt=it.get("delta_font_size_pt", delta_font_size_pt),
                compact=it.get("compact", compact),
            )
            fragments.append(fragment)
            per_tile_meta.append(
                {
                    "auto_shrunk_value_font": used_font != float(requested_value_font),
                    "value_font_used_pt": used_font,
                }
            )

        # Compose the value dict — list of {bg, label, value, delta} per tile.
        items_value = ", ".join(
            "{"
            f'"background": _t{i}_bg, "label": _t{i}_label, '
            f'"value": _t{i}_value, "delta": _t{i}_delta'
            "}"
            for i in range(len(items))
        )
        body = (
            "import scribus as _s\n"
            + "".join(fragments)
            + f"_value = [{items_value}]\n"
        )

        backend = await get_backend(ctx, mode)
        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "kpi_row script failed"}

        raw_tiles = res.value or []
        out: list[dict] = []
        for tile, meta in zip(raw_tiles, per_tile_meta, strict=False):
            out.append(
                {
                    "ok": True,
                    "background": tile.get("background"),
                    "label": tile.get("label"),
                    "value": tile.get("value"),
                    "delta": tile.get("delta"),
                    **meta,
                }
            )

        return {
            "ok": True,
            "tiles": out,
            "count": len(items),
            "tile_width_mm": bboxes[0]["width_mm"],
            "error": None,
        }

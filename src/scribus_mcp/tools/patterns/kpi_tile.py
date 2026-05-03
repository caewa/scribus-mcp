"""Dashboard KPI tile: small label + big value + optional delta.

Single-script-body design. ``render_kpi_tile`` no longer hits the
backend itself — it builds a script-body *fragment* (using unique
variable names per tile) so a wrapper can either dispatch one tile or
concatenate many fragments and dispatch a whole row in one round-trip.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def render_kpi_tile_script(
    *,
    var_prefix: str,
    value: str,
    label: str,
    x_mm: float,
    y_mm: float,
    width_mm: float = 50.0,
    height_mm: float = 30.0,
    delta: str = "",
    fill_color: str = "Black",
    fill_shade: int = 6,
    value_color: str = "Black",
    value_font_size_pt: float = 24,
    label_color: str = "Black",
    label_font_size_pt: float = 8,
    delta_color: str = "Black",
    delta_font_size_pt: float = 8,
    compact: bool = False,
) -> tuple[str, float]:
    """Build a script-body fragment that draws ONE KPI tile.

    ``var_prefix`` is the unique prefix used for the tile's variable
    names — ``t``, ``t0``, ``t1``, etc. The fragment binds:

      _<prefix>_bg, _<prefix>_label, _<prefix>_value, _<prefix>_delta
      _<prefix>_actual_value_font  (float)

    Returns ``(fragment_string, computed_value_font)``. The wrapper
    composes the fragment into a full script and pulls names back via
    a ``_value`` dict.
    """
    if compact:
        pad_x = 3.0
        pad_top = 2.0
        pad_bottom = 2.0
        gap_label_to_value = 0.5
        gap_value_to_delta = 0.5
    else:
        pad_x = 4.5
        pad_top = 4.0
        pad_bottom = 4.0
        gap_label_to_value = 1.5
        gap_value_to_delta = 2.0
    label_h = max(4.5, label_font_size_pt * 0.6)
    delta_h = max(4.5, delta_font_size_pt * 0.6)

    def _mm_for(font_pt: float) -> float:
        return max(6.5, float(font_pt) * 0.7)

    delta_band = (delta_h + gap_value_to_delta) if delta else 0
    val_band_top = y_mm + pad_top + label_h + gap_label_to_value
    val_band_bottom = y_mm + height_mm - pad_bottom - delta_band
    val_band_h = max(6.5, val_band_bottom - val_band_top)

    actual_value_font = float(value_font_size_pt)
    if _mm_for(actual_value_font) > val_band_h:
        actual_value_font = max(6.0, val_band_h / 0.7)

    text_w = width_mm - 2 * pad_x
    label_text = label.upper()

    fragment_parts = [
        f"_{var_prefix}_bg = _s.createRect({x_mm}, {y_mm}, {width_mm}, {height_mm})",
        f"_s.setFillColor({fill_color!r}, _{var_prefix}_bg)",
        f"_s.setFillShade({int(fill_shade)}, _{var_prefix}_bg)",
        f'_s.setLineColor("None", _{var_prefix}_bg)',
        f"_{var_prefix}_label = _s.createText({x_mm + pad_x}, {y_mm + pad_top}, {text_w}, {label_h})",
        f"_s.setText({label_text!r}, _{var_prefix}_label)",
        f"_s.setFontSize({float(label_font_size_pt)}, _{var_prefix}_label)",
        f"_s.setTextColor({label_color!r}, _{var_prefix}_label)",
        f"_{var_prefix}_value = _s.createText({x_mm + pad_x}, {val_band_top}, {text_w}, {val_band_h})",
        f"_s.setText({str(value)!r}, _{var_prefix}_value)",
        f"_s.setFontSize({actual_value_font}, _{var_prefix}_value)",
        f"_s.setTextColor({value_color!r}, _{var_prefix}_value)",
        f"_s.setTextVerticalAlignment(1, _{var_prefix}_value)",
    ]
    if delta:
        delta_y = y_mm + height_mm - pad_bottom - delta_h
        fragment_parts.extend(
            [
                f"_{var_prefix}_delta = _s.createText({x_mm + pad_x}, {delta_y}, {text_w}, {delta_h})",
                f"_s.setText({delta!r}, _{var_prefix}_delta)",
                f"_s.setFontSize({float(delta_font_size_pt)}, _{var_prefix}_delta)",
                f"_s.setTextColor({delta_color!r}, _{var_prefix}_delta)",
            ]
        )
    else:
        fragment_parts.append(f"_{var_prefix}_delta = None")

    return "\n".join(fragment_parts) + "\n", actual_value_font


# Backwards-compat alias (kpi_row imports this name).
async def render_kpi_tile(
    backend,
    *,
    value: str,
    label: str,
    x_mm: float,
    y_mm: float,
    width_mm: float = 50.0,
    height_mm: float = 30.0,
    delta: str = "",
    fill_color: str = "Black",
    fill_shade: int = 6,
    value_color: str = "Black",
    value_font_size_pt: float = 24,
    label_color: str = "Black",
    label_font_size_pt: float = 8,
    delta_color: str = "Black",
    delta_font_size_pt: float = 8,
    compact: bool = False,
) -> dict:
    """Dispatch ONE KPI tile via a single ``backend.script()`` call.

    Used by ``create_kpi_tile``. ``create_kpi_row`` reaches for
    ``render_kpi_tile_script`` directly so it can batch multiple tiles
    into one script.
    """
    fragment, actual_value_font = render_kpi_tile_script(
        var_prefix="t",
        value=value,
        label=label,
        x_mm=x_mm,
        y_mm=y_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        delta=delta,
        fill_color=fill_color,
        fill_shade=fill_shade,
        value_color=value_color,
        value_font_size_pt=value_font_size_pt,
        label_color=label_color,
        label_font_size_pt=label_font_size_pt,
        delta_color=delta_color,
        delta_font_size_pt=delta_font_size_pt,
        compact=compact,
    )
    body = (
        "import scribus as _s\n"
        + fragment
        + '_value = {"background": _t_bg, "label": _t_label, "value": _t_value, "delta": _t_delta}\n'
    )
    res = await backend.script(body, result_expr="_value")
    if not res.ok:
        return {"ok": False, "error": res.error or "kpi_tile script failed"}
    out = res.value or {}
    return {
        "ok": True,
        "background": out.get("background"),
        "label": out.get("label"),
        "value": out.get("value"),
        "delta": out.get("delta"),
        "auto_shrunk_value_font": actual_value_font != float(value_font_size_pt),
        "value_font_used_pt": actual_value_font,
        "error": None,
    }


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_kpi_tile(
        value: str,
        label: str,
        x_mm: float,
        y_mm: float,
        width_mm: float = 50.0,
        height_mm: float = 30.0,
        delta: str = "",
        fill_color: str = "Black",
        fill_shade: int = 6,
        value_color: str = "Black",
        value_font_size_pt: float = 24,
        label_color: str = "Black",
        label_font_size_pt: float = 8,
        delta_color: str = "Black",
        delta_font_size_pt: float = 8,
        compact: bool = False,
        mode: Mode = "auto",
    ) -> dict:
        """Dashboard KPI tile — see ``render_kpi_tile_script`` for the algorithm.

        The value font auto-shrinks if the requested point size won't fit the
        available vertical band — returns ``auto_shrunk_value_font`` and
        ``value_font_used_pt`` so callers can detect it.

        ``compact=True`` halves padding + gaps for dense dashboards. Pair
        with smaller ``value_font_size_pt`` (e.g. 18) and a shorter
        ``height_mm`` (e.g. 22) for a row of compact KPIs.
        """
        backend = await get_backend(ctx, mode)
        return await render_kpi_tile(
            backend,
            value=value,
            label=label,
            x_mm=x_mm,
            y_mm=y_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            delta=delta,
            fill_color=fill_color,
            fill_shade=fill_shade,
            value_color=value_color,
            value_font_size_pt=value_font_size_pt,
            label_color=label_color,
            label_font_size_pt=label_font_size_pt,
            delta_color=delta_color,
            delta_font_size_pt=delta_font_size_pt,
            compact=compact,
        )

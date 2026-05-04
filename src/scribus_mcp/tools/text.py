from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

ALIGN = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}

# Scribus's LineSpacingMode enum.
LINE_SPACING_MODE = {"fixed": 0, "automatic": 1, "baseline": 2}

# Scribus's FirstLineOffsetPolicy enum.
FIRST_LINE_OFFSET = {
    "real_glyph_height": 0,
    "font_ascent": 1,
    "line_spacing": 2,
    "baseline_grid": 3,
}


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def set_text(name: str, text: str, mode: Mode = "auto") -> dict:
        """Replace the text content of a text frame."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setText", text, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def append_text(name: str, text: str, mode: Mode = "auto") -> dict:
        """Append text to the end of a text frame."""
        backend = await get_backend(ctx, mode)
        result = await backend.script(
            f"_value = scribus.insertText({text!r}, -1, {name!r})",
            result_expr="_value",
        )
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_text(name: str, mode: Mode = "auto") -> dict:
        """Return the full text of a text frame's story.

        Uses getAllText (full story) rather than getFrameText (visible text
        only). getFrameText returns empty until Scribus has laid the frame
        out, which is unreliable for round-tripping after set_text.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("getAllText", name)
        return {"ok": result.ok, "text": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_visible_text(name: str, mode: Mode = "auto") -> dict:
        """Return only the text currently rendered inside the frame.

        Useful for measuring overflow visually, but may be empty if the
        frame hasn't been laid out yet.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("getFrameText", name)
        return {"ok": result.ok, "text": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def link_text_frames(from_frame: str, to_frame: str, mode: Mode = "auto") -> dict:
        """Link two text frames so text flows between them."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("linkTextFrames", from_frame, to_frame)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def is_text_overflowing(name: str, mode: Mode = "auto") -> dict:
        """Return whether the frame has overset text."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("textOverflows", name)
        return {"ok": result.ok, "overflowing": bool(result.unwrap_or()), "error": None}

    @mcp.tool()
    async def set_font(name: str, font: str, mode: Mode = "auto") -> dict:
        """Set the font of a text frame (must be a font Scribus has loaded)."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setFont", font, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_font_size(name: str, size_pt: float, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("setFontSize", size_pt, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_font_size(name: str, mode: Mode = "auto") -> dict:
        """Return ``{size_pt}`` — the frame's current point size."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("getFontSize", name)
        return {
            "ok": result.ok,
            "size_pt": result.unwrap_or(),
            "error": result.error,
        }

    @mcp.tool()
    async def set_text_color(name: str, color: str, mode: Mode = "auto") -> dict:
        """Set the text fill color (must be a defined color name in the document)."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setTextColor", color, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_text_shade(name: str, shade: int, mode: Mode = "auto") -> dict:
        """Tint the text fill 0–100 (% of the base color).

        Not all Scribus builds expose ``setTextShade``; on those builds
        the call returns an error and the visual stays at 100%.
        """
        if not 0 <= shade <= 100:
            return {"ok": False, "error": "shade must be between 0 and 100"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setTextShade", int(shade), name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_text_alignment(
        name: str,
        alignment: str = "left",
        mode: Mode = "auto",
    ) -> dict:
        """alignment: left | center | right | justify | forced"""
        if alignment not in ALIGN:
            return {
                "ok": False,
                "error": f"alignment must be one of {sorted(ALIGN)}",
            }
        backend = await get_backend(ctx, mode)
        result = await backend.call("setTextAlignment", ALIGN[alignment], name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_spacing(name: str, leading_pt: float, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineSpacing", leading_pt, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_spacing_mode(
        name: str,
        spacing_mode: str = "fixed",
        mode: Mode = "auto",
    ) -> dict:
        """Set how Scribus computes line spacing for the frame.

        ``spacing_mode``:
        - ``fixed``: use the exact leading set by ``set_line_spacing``.
        - ``automatic``: derive leading from the font metrics (typical default).
        - ``baseline``: snap each line to the document's baseline grid.
        """
        if spacing_mode not in LINE_SPACING_MODE:
            return {
                "ok": False,
                "error": f"spacing_mode must be one of {sorted(LINE_SPACING_MODE)}",
            }
        backend = await get_backend(ctx, mode)
        result = await backend.call(
            "setLineSpacingMode", LINE_SPACING_MODE[spacing_mode], name
        )
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_columns(name: str, count: int, mode: Mode = "auto") -> dict:
        """Set how many text columns the frame is split into (>= 1)."""
        if count < 1:
            return {"ok": False, "error": "count must be >= 1"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setColumns", int(count), name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_column_gap(name: str, gap_mm: float, mode: Mode = "auto") -> dict:
        """Set the gap (gutter) between text columns in mm.

        Forces the document unit to mm before the call so ``gap_mm``
        always means millimetres regardless of the doc's current unit.
        """
        if gap_mm < 0:
            return {"ok": False, "error": "gap_mm must be >= 0"}
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            "try:\n"
            "    _s.setUnit(_s.UNIT_MILLIMETERS)\n"
            "except Exception:\n"
            "    pass\n"
            f"_value = _s.setColumnGap({gap_mm}, {name!r})\n"
        )
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_underline(
        name: str,
        offset_hpt: int = -1,
        width_hpt: int = -1,
        mode: Mode = "auto",
    ) -> dict:
        """Apply an underline to all text in the frame.

        ``offset_hpt`` and ``width_hpt`` are in **hundredths of a point**
        (Scribus's convention). Pass ``-1`` for either to use the font's
        default underline metrics. See ``set_underline_pt`` for a
        point-based variant.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("setUnderline", int(offset_hpt), int(width_hpt), name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_underline_pt(
        name: str,
        offset_pt: float = -1.0,
        width_pt: float = -1.0,
        mode: Mode = "auto",
    ) -> dict:
        """Apply an underline using point measurements.

        ``offset_pt`` is the distance below the baseline; ``width_pt`` is
        the line thickness. Pass ``-1.0`` for either to use the font's
        default. Internally multiplied by 100 (Scribus stores these as
        1/100 pt).
        """
        backend = await get_backend(ctx, mode)
        offset_hpt = -1 if offset_pt == -1.0 else round(offset_pt * 100)
        width_hpt = -1 if width_pt == -1.0 else round(width_pt * 100)
        result = await backend.call("setUnderline", offset_hpt, width_hpt, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_strikethrough(
        name: str,
        offset_hpt: int = -1,
        width_hpt: int = -1,
        mode: Mode = "auto",
    ) -> dict:
        """Apply strikethrough to all text in the frame.

        ``offset_hpt`` and ``width_hpt`` are in hundredths of a point;
        ``-1`` means font default (same convention as ``set_underline``).
        See ``set_strikethrough_pt`` for a point-based variant.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call(
            "setStrikethru", int(offset_hpt), int(width_hpt), name
        )
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_strikethrough_pt(
        name: str,
        offset_pt: float = -1.0,
        width_pt: float = -1.0,
        mode: Mode = "auto",
    ) -> dict:
        """Apply strikethrough using point measurements.

        Pass ``-1.0`` for either arg to use the font's default. Same
        conversion as ``set_underline_pt`` (× 100 → Scribus's 1/100 pt).
        """
        backend = await get_backend(ctx, mode)
        offset_hpt = -1 if offset_pt == -1.0 else round(offset_pt * 100)
        width_hpt = -1 if width_pt == -1.0 else round(width_pt * 100)
        result = await backend.call("setStrikethru", offset_hpt, width_hpt, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_outline(name: str, width_hpt: int, mode: Mode = "auto") -> dict:
        """Set the outline (stroke) width for text in the frame.

        ``width_hpt`` is in hundredths of a point. ``0`` disables the
        outline; positive values draw a stroke that thickness around
        each glyph. See ``set_outline_pt`` for a point-based variant.
        """
        if width_hpt < 0:
            return {"ok": False, "error": "width_hpt must be >= 0"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setOutline", int(width_hpt), name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_outline_pt(name: str, width_pt: float, mode: Mode = "auto") -> dict:
        """Set the text outline width in points. ``0.0`` disables the outline."""
        if width_pt < 0:
            return {"ok": False, "error": "width_pt must be >= 0"}
        backend = await get_backend(ctx, mode)
        width_hpt = round(width_pt * 100)
        result = await backend.call("setOutline", width_hpt, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_shadow(
        name: str,
        x_offset_hpt: int,
        y_offset_hpt: int,
        mode: Mode = "auto",
    ) -> dict:
        """Set drop-shadow offsets for text in the frame.

        Both offsets are in hundredths of a point. Positive ``y_offset_hpt``
        moves the shadow down; positive ``x_offset_hpt`` moves it right.
        See ``set_shadow_pt`` for a point-based variant.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call(
            "setShadow", int(x_offset_hpt), int(y_offset_hpt), name
        )
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_shadow_pt(
        name: str,
        x_offset_pt: float,
        y_offset_pt: float,
        mode: Mode = "auto",
    ) -> dict:
        """Set drop-shadow offsets in points.

        Positive ``y_offset_pt`` moves the shadow down; positive
        ``x_offset_pt`` moves it right.
        """
        backend = await get_backend(ctx, mode)
        x_hpt = round(x_offset_pt * 100)
        y_hpt = round(y_offset_pt * 100)
        result = await backend.call("setShadow", x_hpt, y_hpt, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_text_horizontal_scale(
        name: str,
        scale_percent: float = 100.0,
        mode: Mode = "auto",
    ) -> dict:
        """Stretch/squeeze glyphs horizontally. ``100.0`` = normal width.

        Scribus internally stores this as 1/1000ths; we accept percent
        for the API surface and convert.
        """
        if scale_percent <= 0:
            return {"ok": False, "error": "scale_percent must be > 0"}
        backend = await get_backend(ctx, mode)
        scribus_value = round(scale_percent * 10)
        result = await backend.call("setTextScalingH", scribus_value, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_text_vertical_scale(
        name: str,
        scale_percent: float = 100.0,
        mode: Mode = "auto",
    ) -> dict:
        """Stretch/squeeze glyphs vertically. ``100.0`` = normal height.

        Same 1/1000ths conversion as ``set_text_horizontal_scale``.
        """
        if scale_percent <= 0:
            return {"ok": False, "error": "scale_percent must be > 0"}
        backend = await get_backend(ctx, mode)
        scribus_value = round(scale_percent * 10)
        result = await backend.call("setTextScalingV", scribus_value, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_first_line_offset(
        name: str,
        policy: str = "real_glyph_height",
        mode: Mode = "auto",
    ) -> dict:
        """Choose how the first line of text is offset from the frame's top.

        ``policy``:
        - ``real_glyph_height``: use the actual top of the rendered glyphs (default).
        - ``font_ascent``: use the font's ascender metric.
        - ``line_spacing``: offset by one full line's spacing.
        - ``baseline_grid``: snap to the document baseline grid.
        """
        if policy not in FIRST_LINE_OFFSET:
            return {
                "ok": False,
                "error": f"policy must be one of {sorted(FIRST_LINE_OFFSET)}",
            }
        backend = await get_backend(ctx, mode)
        result = await backend.call(
            "setFirstLineOffset", FIRST_LINE_OFFSET[policy], name
        )
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_text_vertical_alignment(
        name: str,
        alignment: str = "top",
        mode: Mode = "auto",
    ) -> dict:
        """Vertical alignment of text inside a frame ∈ {top, center, bottom}.

        Useful when centering small text (page numbers, badge digits, KPI
        labels) inside a fixed-size frame — the default is top, which leaves
        text hugging the upper edge."""
        align_map = {"top": 0, "center": 1, "centered": 1, "middle": 1, "bottom": 2}
        if alignment not in align_map:
            return {"ok": False, "error": f"alignment must be one of {sorted(set(align_map))}"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setTextVerticalAlignment", align_map[alignment], name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

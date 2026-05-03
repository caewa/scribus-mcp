from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

ALIGN = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}


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
    async def set_text_color(name: str, color: str, mode: Mode = "auto") -> dict:
        """Set the text fill color (must be a defined color name in the document)."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setTextColor", color, name)
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

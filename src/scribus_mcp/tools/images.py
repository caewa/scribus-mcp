from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def load_image(name: str, path: str, mode: Mode = "auto") -> dict:
        """Load an image file into an existing image frame."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("loadImage", path, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_image_file(name: str, mode: Mode = "auto") -> dict:
        """Return ``{path}`` of the image currently loaded in the frame.

        Empty string if no image is loaded. The path may be relative to
        the document if it was stored that way at load time.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("getImageFile", name)
        return {"ok": result.ok, "path": result.unwrap_or() or "", "error": result.error}

    @mcp.tool()
    async def set_image_scale(
        name: str, x_scale: float, y_scale: float, mode: Mode = "auto"
    ) -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("setImageScale", x_scale, y_scale, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def scale_image_to_frame(
        name: str,
        proportional: bool = True,
        mode: Mode = "auto",
    ) -> dict:
        """Make the loaded image fit the frame, optionally preserving aspect ratio."""
        backend = await get_backend(ctx, mode)
        # setScaleImageToFrame(scaleToFrame, proportional, name)
        result = await backend.call("setScaleImageToFrame", 1, 1 if proportional else 0, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_image_offset(
        name: str, offset_x_mm: float, offset_y_mm: float, mode: Mode = "auto"
    ) -> dict:
        """Shift the image inside its frame by ``(offset_x_mm, offset_y_mm)``.

        These are not page coordinates — they're the image's offset
        relative to the frame's top-left.

        Scribus's ``setImageOffset`` interprets the values in the
        document's *current* unit. We force mm before the call so the
        ``_mm`` parameter names mean what they say even if the doc was
        opened in a non-mm unit.
        """
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            "try:\n"
            "    _s.setUnit(_s.UNIT_MILLIMETERS)\n"
            "except Exception:\n"
            "    pass\n"
            f"_value = _s.setImageOffset({offset_x_mm}, {offset_y_mm}, {name!r})\n"
        )
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

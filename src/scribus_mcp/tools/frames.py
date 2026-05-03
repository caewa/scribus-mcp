from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_text_frame(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create a text frame on the current page. Returns the frame name."""
        backend = await get_backend(ctx, mode)
        if name:
            result = await backend.call("createText", x_mm, y_mm, width_mm, height_mm, name)
        else:
            result = await backend.call("createText", x_mm, y_mm, width_mm, height_mm)
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_image_frame(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create an image frame on the current page. Returns the frame name."""
        backend = await get_backend(ctx, mode)
        if name:
            result = await backend.call("createImage", x_mm, y_mm, width_mm, height_mm, name)
        else:
            result = await backend.call("createImage", x_mm, y_mm, width_mm, height_mm)
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def delete_object(name: str, mode: Mode = "auto") -> dict:
        """Delete the named object."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("deleteObject", name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def move_object(
        name: str,
        x_mm: float,
        y_mm: float,
        absolute: bool = False,
        mode: Mode = "auto",
    ) -> dict:
        """Move the object.

        ``absolute=True`` (default False): treats ``x_mm`` / ``y_mm`` as
        the new top-left position on the page (uses ``moveObjectAbs``).

        ``absolute=False``: treats ``x_mm`` / ``y_mm`` as a delta
        relative to the object's current position (uses ``moveObject``).
        """
        backend = await get_backend(ctx, mode)
        method = "moveObjectAbs" if absolute else "moveObject"
        result = await backend.call(method, x_mm, y_mm, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def resize_object(
        name: str,
        width_mm: float,
        height_mm: float,
        mode: Mode = "auto",
    ) -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("sizeObject", width_mm, height_mm, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def rotate_object(
        name: str,
        degrees: float,
        absolute: bool = False,
        mode: Mode = "auto",
    ) -> dict:
        """Rotate clockwise. absolute=True sets angle; absolute=False adds delta."""
        backend = await get_backend(ctx, mode)
        method = "rotateObjectAbs" if absolute else "rotateObject"
        result = await backend.call(method, degrees, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def list_page_objects(mode: Mode = "auto") -> dict:
        """Return the objects on the current page as [{name, type}].

        Propagates the underlying ``ok`` and ``error`` so callers can
        distinguish "empty page" from "failed to query Scribus".
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("getPageItems")
        items = result.unwrap_or() or []
        # getPageItems returns tuples (name, type, page_position). Normalize to dicts.
        normalized = []
        for item in items:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                normalized.append({"name": item[0], "type": item[1]})
            else:
                normalized.append({"raw": item})
        return {"ok": result.ok, "items": normalized, "error": result.error}

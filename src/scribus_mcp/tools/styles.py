from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def list_paragraph_styles(mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("getParagraphStyles")
        return {"ok": result.ok, "styles": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def list_character_styles(mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("getCharStyles")
        return {"ok": result.ok, "styles": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def apply_paragraph_style(name: str, style: str, mode: Mode = "auto") -> dict:
        """Apply a paragraph style by name to a text frame."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setParagraphStyle", style, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def apply_character_style(name: str, style: str, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("setCharacterStyle", style, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def import_styles_from_file(path: str, mode: Mode = "auto") -> dict:
        """Load paragraph styles from another .sla document into the current one."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("loadStylesFromFile", path)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

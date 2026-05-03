from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def add_page(
        position: int = -1,
        master_page: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Add a new page. position=-1 appends at the end. Optional master page name."""
        backend = await get_backend(ctx, mode)
        if master_page:
            result = await backend.call("newPage", position, master_page)
        else:
            result = await backend.call("newPage", position)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def delete_page(page_number: int, mode: Mode = "auto") -> dict:
        """Delete the given page (1-indexed)."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("deletePage", page_number)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def goto_page(page_number: int, mode: Mode = "auto") -> dict:
        """Make page_number (1-indexed) the active working page."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("gotoPage", page_number)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_page_count(mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("pageCount")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def apply_master_page(
        master_page_name: str,
        page_number: int,
        mode: Mode = "auto",
    ) -> dict:
        """Apply a master page to a specific page (1-indexed)."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("applyMasterPage", master_page_name, page_number)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def list_master_pages(mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("masterPageNames")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_master_page(name: str, mode: Mode = "auto") -> dict:
        """Create and open a new master page for editing."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("createMasterPage", name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

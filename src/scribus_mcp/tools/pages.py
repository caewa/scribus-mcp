from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

_FORCE_MM = (
    "import scribus as _s\n"
    "try:\n"
    "    _s.setUnit(_s.UNIT_MILLIMETERS)\n"
    "except Exception:\n"
    "    pass\n"
)

_MOVE_POSITION = {"before": 0, "after": 1, "at_end": 2}


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
    async def get_current_page(mode: Mode = "auto") -> dict:
        """Return the 1-indexed number of the active working page."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("currentPage")
        return {"ok": result.ok, "page": result.unwrap_or(), "error": result.error}

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

    @mcp.tool()
    async def delete_master_page(name: str, mode: Mode = "auto") -> dict:
        """Delete a master page by name."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("deleteMasterPage", name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def move_page(
        from_page: int,
        to_page: int,
        position: str = "after",
        mode: Mode = "auto",
    ) -> dict:
        """Reorder a page (1-indexed).

        ``position`` controls where ``from_page`` lands relative to
        ``to_page``: ``before`` | ``after`` | ``at_end`` (the last
        ignores ``to_page`` and appends).
        """
        if position not in _MOVE_POSITION:
            return {"ok": False, "error": f"position must be one of {sorted(_MOVE_POSITION)}"}
        backend = await get_backend(ctx, mode)
        result = await backend.call(
            "movePage", from_page, to_page, _MOVE_POSITION[position]
        )
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_page_size(mode: Mode = "auto") -> dict:
        """Return ``{width_mm, height_mm}`` of the current page.

        Forces the document unit to mm before reading.
        """
        backend = await get_backend(ctx, mode)
        body = _FORCE_MM + "_value = list(_s.getPageSize())\n"
        result = await backend.script(body, result_expr="_value")
        size = result.unwrap_or() or [None, None]
        return {
            "ok": result.ok,
            "width_mm": size[0],
            "height_mm": size[1],
            "error": result.error,
        }

    @mcp.tool()
    async def get_page_margins(mode: Mode = "auto") -> dict:
        """Return the current page's margins as ``{top_mm, left_mm, right_mm, bottom_mm}``.

        Scribus's ``getPageMargins`` returns ``(top, left, right, bottom)``
        in the document's current unit. We force mm before reading.
        """
        backend = await get_backend(ctx, mode)
        body = _FORCE_MM + "_value = list(_s.getPageMargins())\n"
        result = await backend.script(body, result_expr="_value")
        m = result.unwrap_or() or [None, None, None, None]
        return {
            "ok": result.ok,
            "top_mm": m[0],
            "left_mm": m[1],
            "right_mm": m[2],
            "bottom_mm": m[3],
            "error": result.error,
        }

    @mcp.tool()
    async def set_page_margins(
        top_mm: float,
        left_mm: float,
        right_mm: float,
        bottom_mm: float,
        mode: Mode = "auto",
    ) -> dict:
        """Set the current page's margins (mm).

        Scribus's ``setPageMargins`` C signature takes ``(left, right, top,
        bottom)`` — the inverse order of ``getPageMargins``. This wrapper
        reorders the args for you so the kwargs read naturally.
        """
        backend = await get_backend(ctx, mode)
        body = (
            _FORCE_MM
            + f"_value = _s.setPageMargins({left_mm}, {right_mm}, {top_mm}, {bottom_mm})\n"
        )
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_horizontal_guides(mode: Mode = "auto") -> dict:
        """Return ``{guides_mm}`` — y-positions of horizontal guides on the current page."""
        backend = await get_backend(ctx, mode)
        body = _FORCE_MM + "_value = list(_s.getHGuides() or [])\n"
        result = await backend.script(body, result_expr="_value")
        return {
            "ok": result.ok,
            "guides_mm": result.unwrap_or() or [],
            "error": result.error,
        }

    @mcp.tool()
    async def set_horizontal_guides(positions_mm: list[float], mode: Mode = "auto") -> dict:
        """Replace the page's horizontal guides with the given y-positions (mm)."""
        backend = await get_backend(ctx, mode)
        body = _FORCE_MM + f"_value = _s.setHGuides({list(positions_mm)!r})\n"
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_vertical_guides(mode: Mode = "auto") -> dict:
        """Return ``{guides_mm}`` — x-positions of vertical guides on the current page."""
        backend = await get_backend(ctx, mode)
        body = _FORCE_MM + "_value = list(_s.getVGuides() or [])\n"
        result = await backend.script(body, result_expr="_value")
        return {
            "ok": result.ok,
            "guides_mm": result.unwrap_or() or [],
            "error": result.error,
        }

    @mcp.tool()
    async def set_vertical_guides(positions_mm: list[float], mode: Mode = "auto") -> dict:
        """Replace the page's vertical guides with the given x-positions (mm)."""
        backend = await get_backend(ctx, mode)
        body = _FORCE_MM + f"_value = _s.setVGuides({list(positions_mm)!r})\n"
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

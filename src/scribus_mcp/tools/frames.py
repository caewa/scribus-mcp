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
    async def scale_group(name: str, factor: float, mode: Mode = "auto") -> dict:
        """Scale a group proportionally by ``factor`` (1.0 = no change).

        ``name`` must refer to an object that is part of a group; Scribus
        scales the entire group around its origin.
        """
        if factor <= 0:
            return {"ok": False, "error": "factor must be > 0"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("scaleGroup", factor, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def is_object_locked(name: str, mode: Mode = "auto") -> dict:
        """Return ``{locked: bool}`` for the named object."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("isLocked", name)
        return {
            "ok": result.ok,
            "locked": bool(result.unwrap_or()),
            "error": result.error,
        }

    @mcp.tool()
    async def set_object_locked(name: str, locked: bool, mode: Mode = "auto") -> dict:
        """Set whether the named object is locked for editing.

        Scribus's ``lockObject`` is a toggle, not a setter — this wrapper
        reads the current state via ``isLocked`` and only flips it if
        the desired value differs, so the call is idempotent.
        """
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            f"_n = {name!r}\n"
            f"_target = {bool(locked)!r}\n"
            "_current = bool(_s.isLocked(_n))\n"
            "if _current != _target:\n"
            "    _s.lockObject(_n)\n"
            "_value = bool(_s.isLocked(_n))\n"
        )
        result = await backend.script(body, result_expr="_value")
        return {
            "ok": result.ok,
            "locked": bool(result.unwrap_or()),
            "error": result.error,
        }

    @mcp.tool()
    async def get_object_name(name: str, mode: Mode = "auto") -> dict:
        """Return ``{name}`` — the object's actual ``itemName``.

        Usually equal to the input ``name``, but may differ if Scribus
        disambiguated a duplicate at creation time. Useful as a sanity
        check after ``rename_object``.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("getName", name)
        return {
            "ok": result.ok,
            "name": result.unwrap_or() or "",
            "error": result.error,
        }

    @mcp.tool()
    async def rename_object(old_name: str, new_name: str, mode: Mode = "auto") -> dict:
        """Rename an object. Returns ``{name}`` of the new (possibly disambiguated) name.

        Scribus appends a suffix if ``new_name`` collides with an
        existing object, so the returned name is authoritative.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("renameObject", old_name, new_name)
        return {
            "ok": result.ok,
            "name": result.unwrap_or() or "",
            "error": result.error,
        }

    @mcp.tool()
    async def get_object_position(name: str, mode: Mode = "auto") -> dict:
        """Return ``{x_mm, y_mm}`` of the object's top-left corner.

        Forces the document unit to mm before reading so the values
        always mean millimeters regardless of the doc's current unit.
        """
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            "try:\n"
            "    _s.setUnit(_s.UNIT_MILLIMETERS)\n"
            "except Exception:\n"
            "    pass\n"
            f"_value = list(_s.getPosition({name!r}))\n"
        )
        result = await backend.script(body, result_expr="_value")
        pos = result.unwrap_or() or [None, None]
        return {
            "ok": result.ok,
            "x_mm": pos[0],
            "y_mm": pos[1],
            "error": result.error,
        }

    @mcp.tool()
    async def get_object_size(name: str, mode: Mode = "auto") -> dict:
        """Return ``{width_mm, height_mm}`` of the object's bounding box.

        Forces the document unit to mm before reading.
        """
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            "try:\n"
            "    _s.setUnit(_s.UNIT_MILLIMETERS)\n"
            "except Exception:\n"
            "    pass\n"
            f"_value = list(_s.getSize({name!r}))\n"
        )
        result = await backend.script(body, result_expr="_value")
        size = result.unwrap_or() or [None, None]
        return {
            "ok": result.ok,
            "width_mm": size[0],
            "height_mm": size[1],
            "error": result.error,
        }

    @mcp.tool()
    async def object_exists(name: str, mode: Mode = "auto") -> dict:
        """Return ``{exists: bool}`` for the given object name."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("objectExists", name)
        return {
            "ok": result.ok,
            "exists": bool(result.unwrap_or()),
            "error": result.error,
        }

    @mcp.tool()
    async def group_objects(names: list[str], mode: Mode = "auto") -> dict:
        """Group the named objects. Returns ``{name}`` of the new group.

        Captures page items before/after the group call to discover the
        generated group name (Scribus's ``groupObjects`` returns ``None``).
        """
        if not names:
            return {"ok": False, "error": "names must contain at least one object"}
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            f"_names = {list(names)!r}\n"
            "_before = set(_it[0] for _it in (_s.getPageItems() or []))\n"
            "_s.groupObjects(_names)\n"
            "_after = set(_it[0] for _it in (_s.getPageItems() or []))\n"
            "_new = sorted(_after - _before - set(_names))\n"
            "_value = _new[-1] if _new else None\n"
        )
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def outline_text(name: str, mode: Mode = "auto") -> dict:
        """Convert a text frame to vector polygon outlines.

        Replaces the original text frame with one polygon per glyph
        (named ``<orig>+U0``, ``+U1``, ...). Returns ``{names}`` of the
        polygons created so callers can group/move/recolor them.
        """
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            "_before = set(_it[0] for _it in (_s.getPageItems() or []))\n"
            f"_s.layoutText({name!r})\n"
            f"_s.traceText({name!r})\n"
            "_after = set(_it[0] for _it in (_s.getPageItems() or []))\n"
            "_value = sorted(_after - _before)\n"
        )
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "names": result.unwrap_or() or [], "error": result.error}

    @mcp.tool()
    async def layout_text(name: str, chain: bool = False, mode: Mode = "auto") -> dict:
        """Force a text frame to (re-)lay out its content.

        ``chain=True`` lays out the entire linked chain starting at
        ``name`` (uses ``layoutTextChain``); otherwise just the single
        frame (``layoutText``). Useful before reading geometry-derived
        values like ``getSize`` on outlined text.
        """
        backend = await get_backend(ctx, mode)
        method = "layoutTextChain" if chain else "layoutText"
        result = await backend.call(method, name)
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

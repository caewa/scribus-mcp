from __future__ import annotations

from typing import Annotated

from pydantic import Field

from scribus_mcp.tools._common import (
    Mode,
    ServerCtx,
    get_backend,
    probe_scribus_version,
)
from scribus_mcp.tools.palette import invalidate_palette

UNIT_MM = 1  # scribus.UNIT_MILLIMETERS
FACING_PAGES_NO = 0
FIRST_PAGE_LEFT = 0
ORIENTATION_PORTRAIT = 0
ORIENTATION_LANDSCAPE = 1

# Scribus unit constants. Strings used as the public surface of
# get_unit / set_unit so callers don't deal with raw ints.
UNIT_NAMES: dict[str, int] = {
    "pt": 0,  # points
    "mm": 1,  # millimetres
    "in": 2,  # inches
    "p": 3,  # picas
    "cm": 4,  # centimetres
    "c": 5,  # ciceros
}
UNIT_INTS: dict[int, str] = {v: k for k, v in UNIT_NAMES.items()}


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_document(
        width_mm: Annotated[float, Field(gt=0, le=10000)] = 210.0,
        height_mm: Annotated[float, Field(gt=0, le=10000)] = 297.0,
        margin_top_mm: float = 15.0,
        margin_left_mm: float = 15.0,
        margin_right_mm: float = 15.0,
        margin_bottom_mm: float = 20.0,
        orientation: Annotated[str, Field(pattern="^(portrait|landscape)$")] = "portrait",
        first_page_number: int = 1,
        facing_pages: bool = False,
        pages: Annotated[int, Field(ge=1, le=1000)] = 1,
        mode: Mode = "auto",
    ) -> dict:
        """Create a new Scribus document. Coordinates are in millimeters.

        ``pages`` is the initial page count (1..1000). Use ``add_page``
        later to insert more or ``delete_page`` to drop them.
        """
        backend = await get_backend(ctx, mode)
        # newDocument(size, margins, orientation, firstPageNum, unit, facingPages, firstPageOrder, numPages)
        # size = (w, h), margins = (left, right, top, bottom)
        size = (width_mm, height_mm)
        margins = (margin_left_mm, margin_right_mm, margin_top_mm, margin_bottom_mm)
        orient = ORIENTATION_LANDSCAPE if orientation == "landscape" else ORIENTATION_PORTRAIT
        result = await backend.call(
            "newDocument",
            size,
            margins,
            orient,
            first_page_number,
            UNIT_MM,
            1 if facing_pages else FACING_PAGES_NO,
            FIRST_PAGE_LEFT,
            int(pages),
        )
        if result.ok:
            invalidate_palette(backend)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def open_document(path: str, mode: Mode = "auto") -> dict:
        """Open an existing .sla document.

        If the document at ``path`` is already the active document in an
        interactive Scribus session, this is a no-op — calling Scribus's
        ``openDoc`` again on a path that's already open pops a modal
        ("Ce document est déjà ouvert…") that requires user dismissal.
        """
        backend = await get_backend(ctx, mode)
        body = f"""
import os
import scribus as _s

_target = os.path.abspath({path!r})
_already_open = False
try:
    if _s.haveDoc():
        _current = _s.getDocName() or ""
        if _current and os.path.abspath(_current) == _target:
            _already_open = True
except Exception:
    _already_open = False

if not _already_open:
    _s.openDoc(_target)
_value = True
"""
        res = await backend.script(body, result_expr="_value")
        if res.ok:
            invalidate_palette(backend)
        return {"ok": res.ok, "value": res.value, "error": res.error}

    @mcp.tool()
    async def save_document(mode: Mode = "auto") -> dict:
        """Save the current document under its existing filename."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("saveDoc")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def save_document_as(path: str, mode: Mode = "auto") -> dict:
        """Save the current document to a new path."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("saveDocAs", path)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def close_document(mode: Mode = "auto") -> dict:
        """Close the active document without saving."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("closeDoc")
        if result.ok:
            invalidate_palette(backend)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_document_info(mode: Mode = "auto") -> dict:
        """Return basic document metadata (path, page count, dimensions, units)."""
        backend = await get_backend(ctx, mode)
        body = (
            "import scribus as _s\n"
            "_value = {\n"
            "    'path': _s.getDocName(),\n"
            "    'page_count': _s.pageCount(),\n"
            "    'page_size': _s.getPageSize(),\n"
            "    'unit': _s.getUnit(),\n"
            "    'has_doc': bool(_s.haveDoc()),\n"
            "}"
        )
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_scribus_version(mode: Mode = "auto") -> dict:
        """Return the running Scribus's version — useful for the LLM to
        choose between 1.6 and 1.7 codepaths (e.g. ``create_qr_code_block``
        is 1.7+ only).

        Returns ``{ok, major, minor, patch, version, version_string,
        is_17_or_newer}``. ``version`` is the ``(major, minor, patch)``
        tuple as a list; ``version_string`` is the dotted form ``"1.7.3"``.
        ``is_17_or_newer`` is the convenience flag for feature gating.
        Reports ``major=0`` and ``version_string=""`` if the probe failed
        (bridge unreachable, no ``SCRIBUS_VERSION_INFO`` attribute on
        this Scribus build) — treat that as "unknown" / "fail closed".
        """
        backend = await get_backend(ctx, mode)
        version = await probe_scribus_version(backend)
        major, minor, patch = version
        version_string = (
            ".".join(str(n) for n in version) if version != (0, 0, 0) else ""
        )
        return {
            "ok": True,
            "major": major,
            "minor": minor,
            "patch": patch,
            "version": list(version),
            "version_string": version_string,
            "is_17_or_newer": version >= (1, 7, 0),
            "error": None,
        }

    @mcp.tool()
    async def has_document(mode: Mode = "auto") -> dict:
        """Return ``{has_doc: bool}`` — whether any document is currently open."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("haveDoc")
        return {
            "ok": result.ok,
            "has_doc": bool(result.unwrap_or()),
            "error": result.error,
        }

    @mcp.tool()
    async def get_document_name(mode: Mode = "auto") -> dict:
        """Return ``{path}`` — filesystem path of the active document, or empty if unsaved."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("getDocName")
        return {
            "ok": result.ok,
            "path": result.unwrap_or() or "",
            "error": result.error,
        }

    @mcp.tool()
    async def revert_document(mode: Mode = "auto") -> dict:
        """Reload the active document from disk, discarding unsaved edits.

        No-op (and returns an error) if the document has never been
        saved — there's nothing on disk to revert to.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("revertDoc")
        if result.ok:
            invalidate_palette(backend)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_unit(mode: Mode = "auto") -> dict:
        """Return ``{unit}`` — the document's current measurement unit.

        One of: ``pt`` | ``mm`` | ``in`` | ``p`` (picas) | ``cm`` | ``c``
        (ciceros). Returns the raw int as ``unit_int`` too so callers
        can detect unknown future units.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("getUnit")
        raw = result.unwrap_or()
        return {
            "ok": result.ok,
            "unit": UNIT_INTS.get(raw, ""),
            "unit_int": raw,
            "error": result.error,
        }

    @mcp.tool()
    async def set_unit(unit: str, mode: Mode = "auto") -> dict:
        """Set the document's measurement unit.

        ``unit``: ``pt`` | ``mm`` | ``in`` | ``p`` | ``cm`` | ``c``.

        Note: the MCP geometry tools all take and return millimetres
        regardless of this setting — they force mm internally before
        reading. Changing the unit is mainly about how Scribus shows
        and persists coordinates in the saved ``.sla``.
        """
        if unit not in UNIT_NAMES:
            return {"ok": False, "error": f"unit must be one of {sorted(UNIT_NAMES)}"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setUnit", UNIT_NAMES[unit])
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_document_metadata(
        title: str = "",
        author: str = "",
        description: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Set document metadata (used in PDF metadata on export).

        Scribus 1.7's ``setInfo`` takes only (author, description, title)
        — there's no Keywords slot in this Scripter API. If you need
        Keywords, use ``run_script`` to set ``Document.keywords``
        directly.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.call("setInfo", author, description, title)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

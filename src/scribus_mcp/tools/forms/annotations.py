"""Convert text frames into PDF annotations: page links, URI links, file
links, and sticky-note text annotations.

Each tool either:
  (a) takes the name of an existing text frame and annotates it, or
  (b) creates a new text frame for the caller and annotates it in one call.

The shape returned mirrors that — ``mode="apply"`` (default) annotates an
existing frame; ``mode="create"`` creates the frame first.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode as _BackendMode
from scribus_mcp.tools._common import ServerCtx, clean_user_text, get_backend

# Sticky-note icon codes per setTextAnnotation
TEXT_ANNOTATION_ICONS = {
    "note": 0,
    "comment": 1,
    "key": 2,
    "help": 3,
    "newparagraph": 4,
    "paragraph": 5,
    "insert": 6,
    "cross": 7,
    "circle": 8,
}


async def _ensure_frame(backend, name: str, x: float, y: float, w: float, h: float):
    """Return an existing frame's name, or create a new text frame and return
    its name. Used by tools that work either way.
    """
    if name:
        return {"ok": True, "name": name, "created": False, "error": None}
    args = (x, y, w, h)
    res = await backend.call("createText", *args)
    if not res.ok:
        return {"ok": False, "error": f"createText failed: {res.error}"}
    return {"ok": True, "name": res.value, "created": True, "error": None}


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_link_annotation(
        target_page: int,
        target_x_mm: float = 0.0,
        target_y_mm: float = 0.0,
        frame_name: str = "",
        frame_x_mm: float = 0.0,
        frame_y_mm: float = 0.0,
        frame_width_mm: float = 30.0,
        frame_height_mm: float = 6.0,
        link_text: str = "",
        mode: _BackendMode = "auto",
    ) -> dict:
        """Internal page link.

        If ``frame_name`` is empty, a new text frame is created at
        (frame_x, frame_y, frame_width, frame_height) with ``link_text`` as
        its label. Otherwise the named existing frame is annotated.

        ``target_page`` is 1-indexed. ``target_x_mm`` / ``target_y_mm`` is
        the position WITHIN the target page the link jumps to
        (0,0 = top-left). The ``frame_*`` parameters are the position of
        the clickable annotation rectangle on the *current* page.
        """
        backend = await get_backend(ctx, mode)
        f = await _ensure_frame(
            backend, frame_name, frame_x_mm, frame_y_mm, frame_width_mm, frame_height_mm
        )
        if not f.get("ok"):
            return f
        name = f["name"]
        if f.get("created") and link_text:
            await backend.call("setText", clean_user_text(link_text), name)
        # setLinkAnnotation requires all numeric args as int.
        r = await backend.call(
            "setLinkAnnotation",
            int(target_page),
            round(target_x_mm),
            round(target_y_mm),
            name,
        )
        return {
            "ok": r.ok,
            "frame": name,
            "created_frame": f.get("created", False),
            "error": r.error,
        }

    @mcp.tool()
    async def create_uri_annotation(
        uri: str,
        frame_name: str = "",
        frame_x_mm: float = 0.0,
        frame_y_mm: float = 0.0,
        frame_width_mm: float = 30.0,
        frame_height_mm: float = 6.0,
        link_text: str = "",
        mode: _BackendMode = "auto",
    ) -> dict:
        """External URL link. Like ``create_link_annotation`` but jumps to a
        URI instead of a page.
        """
        backend = await get_backend(ctx, mode)
        f = await _ensure_frame(
            backend, frame_name, frame_x_mm, frame_y_mm, frame_width_mm, frame_height_mm
        )
        if not f.get("ok"):
            return f
        name = f["name"]
        if f.get("created") and link_text:
            await backend.call("setText", clean_user_text(link_text), name)
        r = await backend.call("setURIAnnotation", uri, name)
        return {
            "ok": r.ok,
            "frame": name,
            "created_frame": f.get("created", False),
            "error": r.error,
        }

    @mcp.tool()
    async def create_file_annotation(
        path: str,
        target_page: int = 1,
        target_x_mm: float = 0.0,
        target_y_mm: float = 0.0,
        absolute: bool = True,
        frame_name: str = "",
        frame_x_mm: float = 0.0,
        frame_y_mm: float = 0.0,
        frame_width_mm: float = 30.0,
        frame_height_mm: float = 6.0,
        link_text: str = "",
        mode: _BackendMode = "auto",
    ) -> dict:
        """Link to an external file. ``absolute=False`` produces a
        relative-path link, useful for portable PDFs that travel with
        their assets.

        ``target_x_mm`` / ``target_y_mm`` is where on the destination
        page the link jumps to (0,0 = top-left). The ``frame_*``
        parameters are the position of the clickable annotation
        rectangle on the *current* page.
        """
        backend = await get_backend(ctx, mode)
        f = await _ensure_frame(
            backend, frame_name, frame_x_mm, frame_y_mm, frame_width_mm, frame_height_mm
        )
        if not f.get("ok"):
            return f
        name = f["name"]
        if f.get("created") and link_text:
            await backend.call("setText", clean_user_text(link_text), name)
        # setFileAnnotation(path, page, x, y, [name], [absolute=True])
        r = await backend.call(
            "setFileAnnotation",
            path,
            int(target_page),
            round(target_x_mm),
            round(target_y_mm),
            name,
            absolute=absolute,
        )
        return {
            "ok": r.ok,
            "frame": name,
            "created_frame": f.get("created", False),
            "error": r.error,
        }

    @mcp.tool()
    async def create_text_annotation(
        text: str,
        x_mm: float,
        y_mm: float,
        width_mm: float = 8.0,
        height_mm: float = 8.0,
        icon: str = "note",
        is_open: bool = False,
        frame_name: str = "",
        mode: _BackendMode = "auto",
    ) -> dict:
        """Sticky note / comment that pops up when the reader hovers / clicks.

        ``icon`` ∈ {note, comment, key, help, newparagraph, paragraph,
        insert, cross, circle}. ``is_open`` controls whether the note is
        visible by default in the PDF reader.
        """
        if icon not in TEXT_ANNOTATION_ICONS:
            return {"ok": False, "error": f"icon must be one of {sorted(TEXT_ANNOTATION_ICONS)}"}
        backend = await get_backend(ctx, mode)
        f = await _ensure_frame(backend, frame_name, x_mm, y_mm, width_mm, height_mm)
        if not f.get("ok"):
            return f
        name = f["name"]
        if f.get("created"):
            await backend.call("setText", clean_user_text(text), name)
        r = await backend.call(
            "setTextAnnotation", TEXT_ANNOTATION_ICONS[icon], bool(is_open), name
        )
        return {
            "ok": r.ok,
            "frame": name,
            "created_frame": f.get("created", False),
            "error": r.error,
        }

    @mcp.tool()
    async def is_annotated(name: str, mode: _BackendMode = "auto") -> dict:
        """Inspect an object: is it a PDF annotation? If so, what kind, and
        what details has Scribus stored about it. Returns the tuple Scribus
        produces: ``(annotation_type, info_dict)`` or None.
        """
        backend = await get_backend(ctx, mode)
        r = await backend.call("isAnnotated", name)
        return {"ok": r.ok, "info": r.unwrap_or(), "error": r.error}

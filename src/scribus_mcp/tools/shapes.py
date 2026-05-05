"""Shape primitives — rect, ellipse, line, polyline, polygon, bezier.

All ``create_*`` tools return the assigned object name. Coordinates are
in millimetres. For polyline/polygon/bezier, ``points_mm`` is a flat
list ``[x1, y1, x2, y2, ...]``.

Every primitive accepts optional ``fill_color`` / ``fill_shade`` /
``line_color`` / ``line_width_pt`` so callers don't have to round-trip
through ``set_fill_color`` / ``set_line_color`` after creation.
``line_color="None"`` (the Scribus sentinel) draws no stroke and sets
``line_width_pt=0`` automatically. Color slots flow through the same
palette resolver as the high-level patterns / layouts: pass a role
name like ``"primary"`` and it resolves to the matching document color
when defined, falling back to the supplied color otherwise.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.palette import resolve_color


def _validate_points(
    points_mm: list[float], min_numbers: int, group_size: int, kind: str
) -> str | None:
    """Validate a flat coordinate list — return an error message or None
    if valid. ``group_size=2`` for x/y pairs (polygon, polyline);
    ``group_size=4`` for Scribus's bezier (anchor + control)."""
    pts_per_group = group_size // 2
    min_pts = min_numbers // group_size * pts_per_group
    if len(points_mm) < min_numbers or len(points_mm) % group_size != 0:
        if group_size == 2:
            return (
                f"points_mm must contain at least {min_numbers} numbers "
                f"({min_pts} points), in pairs"
            )
        return f"points_mm must contain at least {min_numbers} numbers in groups of {group_size}"
    return None


async def _resolve_styling(
    backend,
    *,
    fill_color: str | None,
    fill_shade: int | None,
    line_color: str | None,
    line_width_pt: float | None,
    has_fill: bool,
) -> tuple[str | None, int | None, str | None, float | None]:
    """Run the palette resolver over every styling slot the caller passed.

    ``has_fill`` is False for line-only shapes (line, polyline, bezier);
    in that case ``fill_color`` / ``fill_shade`` are returned untouched.
    """
    fc, fs = fill_color, fill_shade
    if has_fill and fill_color is not None:
        fc, fs = await resolve_color(
            backend,
            fill_color,
            fallback_shade=100,
            current_shade=fill_shade,
        )
    lc = line_color
    if line_color is not None and line_color != "None":
        lc, _ = await resolve_color(backend, line_color)
    return fc, fs, lc, line_width_pt


def _styling_fragment(
    obj_var: str,
    *,
    fill_color: str | None,
    fill_shade: int | None,
    line_color: str | None,
    line_width_pt: float | None,
    has_fill: bool,
) -> str:
    """Build the post-create styling block for a freshly-created shape.

    Emits ``setFillColor`` / ``setFillShade`` only when ``fill_color``
    is set. Emits ``setLineColor`` / ``setLineWidth`` whenever the
    caller passed ``line_color`` *or* ``line_width_pt`` so callers can
    suppress the default 1pt black stroke with ``line_color="None"``.
    """
    parts: list[str] = []
    if has_fill and fill_color is not None:
        parts.append(f"_s.setFillColor({fill_color!r}, {obj_var})")
        if fill_shade is not None:
            parts.append(f"_s.setFillShade({int(fill_shade)}, {obj_var})")
    if line_color is not None:
        if line_color == "None":
            parts.append(f'_s.setLineColor("None", {obj_var})')
            parts.append(f"_s.setLineWidth(0, {obj_var})")
        else:
            parts.append(f"_s.setLineColor({line_color!r}, {obj_var})")
            if line_width_pt is not None:
                parts.append(f"_s.setLineWidth({float(line_width_pt)}, {obj_var})")
    elif line_width_pt is not None:
        parts.append(f"_s.setLineWidth({float(line_width_pt)}, {obj_var})")
    return "\n".join(parts)


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_rectangle(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        fill_color: str | None = None,
        fill_shade: int | None = None,
        line_color: str | None = None,
        line_width_pt: float | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """Create a rectangle on the current page. Returns the object name.

        Pass ``fill_color`` / ``line_color`` (palette role names like
        ``"primary"`` are accepted) to style at creation time;
        ``line_color="None"`` suppresses the default black stroke.
        """
        backend = await get_backend(ctx, mode)
        fc, fs, lc, lw = await _resolve_styling(
            backend,
            fill_color=fill_color, fill_shade=fill_shade,
            line_color=line_color, line_width_pt=line_width_pt,
            has_fill=True,
        )
        create = (
            f"_v = _s.createRect({x_mm}, {y_mm}, {width_mm}, {height_mm}, {name!r})"
            if name
            else f"_v = _s.createRect({x_mm}, {y_mm}, {width_mm}, {height_mm})"
        )
        styling = _styling_fragment(
            "_v",
            fill_color=fc, fill_shade=fs,
            line_color=lc, line_width_pt=lw,
            has_fill=True,
        )
        body = "import scribus as _s\n" + create + ("\n" + styling if styling else "")
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_ellipse(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        fill_color: str | None = None,
        fill_shade: int | None = None,
        line_color: str | None = None,
        line_width_pt: float | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """Create an ellipse on the current page (bounding box defines axes).

        Same styling args as ``create_rectangle``.
        """
        backend = await get_backend(ctx, mode)
        fc, fs, lc, lw = await _resolve_styling(
            backend,
            fill_color=fill_color, fill_shade=fill_shade,
            line_color=line_color, line_width_pt=line_width_pt,
            has_fill=True,
        )
        create = (
            f"_v = _s.createEllipse({x_mm}, {y_mm}, {width_mm}, {height_mm}, {name!r})"
            if name
            else f"_v = _s.createEllipse({x_mm}, {y_mm}, {width_mm}, {height_mm})"
        )
        styling = _styling_fragment(
            "_v",
            fill_color=fc, fill_shade=fs,
            line_color=lc, line_width_pt=lw,
            has_fill=True,
        )
        body = "import scribus as _s\n" + create + ("\n" + styling if styling else "")
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_line(
        x1_mm: float,
        y1_mm: float,
        x2_mm: float,
        y2_mm: float,
        name: str = "",
        line_color: str | None = None,
        line_width_pt: float | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """Create a straight line from (x1,y1) to (x2,y2).

        Lines have no fill — only ``line_color`` / ``line_width_pt``.
        """
        backend = await get_backend(ctx, mode)
        _, _, lc, lw = await _resolve_styling(
            backend,
            fill_color=None, fill_shade=None,
            line_color=line_color, line_width_pt=line_width_pt,
            has_fill=False,
        )
        create = (
            f"_v = _s.createLine({x1_mm}, {y1_mm}, {x2_mm}, {y2_mm}, {name!r})"
            if name
            else f"_v = _s.createLine({x1_mm}, {y1_mm}, {x2_mm}, {y2_mm})"
        )
        styling = _styling_fragment(
            "_v",
            fill_color=None, fill_shade=None,
            line_color=lc, line_width_pt=lw,
            has_fill=False,
        )
        body = "import scribus as _s\n" + create + ("\n" + styling if styling else "")
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_polygon(
        points_mm: list[float],
        name: str = "",
        fill_color: str | None = None,
        fill_shade: int | None = None,
        line_color: str | None = None,
        line_width_pt: float | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """Create a closed polygon. points_mm is a flat list [x1, y1, x2, y2, ...]
        with at least 3 points (6 numbers)."""
        err = _validate_points(points_mm, min_numbers=6, group_size=2, kind="polygon")
        if err:
            return {"ok": False, "error": err}
        backend = await get_backend(ctx, mode)
        fc, fs, lc, lw = await _resolve_styling(
            backend,
            fill_color=fill_color, fill_shade=fill_shade,
            line_color=line_color, line_width_pt=line_width_pt,
            has_fill=True,
        )
        # Route through script() because Scribus's createPolygon strictly
        # requires a Python list, not a tuple, and our default JSON path
        # converts list args to tuples for geometry compatibility elsewhere.
        pts = list(points_mm)
        create = (
            f"_v = _s.createPolygon({pts!r}, {name!r})"
            if name
            else f"_v = _s.createPolygon({pts!r})"
        )
        styling = _styling_fragment(
            "_v",
            fill_color=fc, fill_shade=fs,
            line_color=lc, line_width_pt=lw,
            has_fill=True,
        )
        body = "import scribus as _s\n" + create + ("\n" + styling if styling else "")
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_polyline(
        points_mm: list[float],
        name: str = "",
        line_color: str | None = None,
        line_width_pt: float | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """Create an open polyline from a flat list of coordinates [x1, y1, x2, y2, ...]
        with at least 2 points (4 numbers).

        Polylines have no fill — only ``line_color`` / ``line_width_pt``.
        """
        err = _validate_points(points_mm, min_numbers=4, group_size=2, kind="polyline")
        if err:
            return {"ok": False, "error": err}
        backend = await get_backend(ctx, mode)
        _, _, lc, lw = await _resolve_styling(
            backend,
            fill_color=None, fill_shade=None,
            line_color=line_color, line_width_pt=line_width_pt,
            has_fill=False,
        )
        pts = list(points_mm)
        create = (
            f"_v = _s.createPolyLine({pts!r}, {name!r})"
            if name
            else f"_v = _s.createPolyLine({pts!r})"
        )
        styling = _styling_fragment(
            "_v",
            fill_color=None, fill_shade=None,
            line_color=lc, line_width_pt=lw,
            has_fill=False,
        )
        body = "import scribus as _s\n" + create + ("\n" + styling if styling else "")
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_bezier_line(
        points_mm: list[float],
        name: str = "",
        line_color: str | None = None,
        line_width_pt: float | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """Create a Bezier curve. points_mm follows Scribus's bezier format:
        groups of 4 numbers (anchor x, anchor y, control x, control y), with
        at least 8 numbers (2 anchors).

        Bezier lines have no fill — only ``line_color`` / ``line_width_pt``.
        """
        err = _validate_points(points_mm, min_numbers=8, group_size=4, kind="bezier")
        if err:
            return {"ok": False, "error": err}
        backend = await get_backend(ctx, mode)
        _, _, lc, lw = await _resolve_styling(
            backend,
            fill_color=None, fill_shade=None,
            line_color=line_color, line_width_pt=line_width_pt,
            has_fill=False,
        )
        pts = list(points_mm)
        create = (
            f"_v = _s.createBezierLine({pts!r}, {name!r})"
            if name
            else f"_v = _s.createBezierLine({pts!r})"
        )
        styling = _styling_fragment(
            "_v",
            fill_color=None, fill_shade=None,
            line_color=lc, line_width_pt=lw,
            has_fill=False,
        )
        body = "import scribus as _s\n" + create + ("\n" + styling if styling else "")
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_path_text(
        text_box: str,
        bezier_curve: str,
        mode: Mode = "auto",
    ) -> dict:
        """Merge a text frame with a bezier curve to make text-on-a-path.
        Both objects are consumed and replaced by a single new object whose
        name is returned."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("createPathText", 0, 0, text_box, bezier_curve)
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

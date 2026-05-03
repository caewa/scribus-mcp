"""Shape primitives — rect, ellipse, line, polyline, polygon, bezier.

All create_* tools return the assigned object name. Coordinates are in
millimetres. For polyline/polygon/bezier, points is a flat list:
``[x1, y1, x2, y2, ...]``.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


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


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_rectangle(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create a rectangle on the current page. Returns the object name."""
        backend = await get_backend(ctx, mode)
        if name:
            result = await backend.call("createRect", x_mm, y_mm, width_mm, height_mm, name)
        else:
            result = await backend.call("createRect", x_mm, y_mm, width_mm, height_mm)
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_ellipse(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create an ellipse on the current page (bounding box defines axes)."""
        backend = await get_backend(ctx, mode)
        if name:
            result = await backend.call("createEllipse", x_mm, y_mm, width_mm, height_mm, name)
        else:
            result = await backend.call("createEllipse", x_mm, y_mm, width_mm, height_mm)
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_line(
        x1_mm: float,
        y1_mm: float,
        x2_mm: float,
        y2_mm: float,
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create a straight line from (x1,y1) to (x2,y2)."""
        backend = await get_backend(ctx, mode)
        if name:
            result = await backend.call("createLine", x1_mm, y1_mm, x2_mm, y2_mm, name)
        else:
            result = await backend.call("createLine", x1_mm, y1_mm, x2_mm, y2_mm)
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_polygon(
        points_mm: list[float],
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create a closed polygon. points_mm is a flat list [x1, y1, x2, y2, ...]
        with at least 3 points (6 numbers)."""
        err = _validate_points(points_mm, min_numbers=6, group_size=2, kind="polygon")
        if err:
            return {"ok": False, "error": err}
        # Route through script() because Scribus's createPolygon strictly
        # requires a Python list, not a tuple, and our default JSON path
        # converts list args to tuples for geometry compatibility elsewhere.
        backend = await get_backend(ctx, mode)
        pts = list(points_mm)
        body = (
            f"_v = scribus.createPolygon({pts!r}, {name!r})"
            if name
            else f"_v = scribus.createPolygon({pts!r})"
        )
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_polyline(
        points_mm: list[float],
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create an open polyline from a flat list of coordinates [x1, y1, x2, y2, ...]
        with at least 2 points (4 numbers)."""
        err = _validate_points(points_mm, min_numbers=4, group_size=2, kind="polyline")
        if err:
            return {"ok": False, "error": err}
        backend = await get_backend(ctx, mode)
        pts = list(points_mm)
        body = (
            f"_v = scribus.createPolyLine({pts!r}, {name!r})"
            if name
            else f"_v = scribus.createPolyLine({pts!r})"
        )
        result = await backend.script(body, result_expr="_v")
        return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def create_bezier_line(
        points_mm: list[float],
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Create a Bezier curve. points_mm follows Scribus's bezier format:
        groups of 4 numbers (anchor x, anchor y, control x, control y), with
        at least 8 numbers (2 anchors)."""
        err = _validate_points(points_mm, min_numbers=8, group_size=4, kind="bezier")
        if err:
            return {"ok": False, "error": err}
        backend = await get_backend(ctx, mode)
        pts = list(points_mm)
        body = (
            f"_v = scribus.createBezierLine({pts!r}, {name!r})"
            if name
            else f"_v = scribus.createBezierLine({pts!r})"
        )
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

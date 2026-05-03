"""Object styling — fill, stroke, line width / style / cap / join,
corner radius, transparency, shade. Applies to any object (text frames,
shapes, image frames).
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

LINE_STYLES = {
    "solid": 1,  # LINE_SOLID
    "dash": 2,  # LINE_DASH
    "dot": 3,  # LINE_DOT
    "dashdot": 4,  # LINE_DASHDOT
    "dashdotdot": 5,  # LINE_DASHDOTDOT
}

LINE_CAPS = {
    "flat": 0,
    "round": 32,
    "square": 16,
}

LINE_JOINS = {
    "miter": 0,
    "round": 128,
    "bevel": 64,
}

GRADIENT_TYPES = {
    "none": 0,  # FILL_NOG — clears the gradient
    "horizontal": 1,  # FILL_HORIZONTALG
    "vertical": 2,  # FILL_VERTICALG
    "diagonal": 3,  # FILL_DIAGONALG
    "cross_diagonal": 4,  # FILL_CROSSDIAGONALG
    "radial": 5,  # FILL_RADIALG
}


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def set_fill_color(name: str, color: str, mode: Mode = "auto") -> dict:
        """Fill color for the named object. Color must be a defined color name
        (e.g. 'Black', 'Brand Deep') or the literal 'None' for transparent."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setFillColor", color, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_color(name: str, color: str, mode: Mode = "auto") -> dict:
        """Stroke/line color for the named object. 'None' for no stroke."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineColor", color, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_fill_shade(name: str, shade_percent: float, mode: Mode = "auto") -> dict:
        """Fill shade (tint) 0–100. 100 is full color, 0 is white tint.
        Scribus's Scripter requires an integer; we round."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setFillShade", round(shade_percent), name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_shade(name: str, shade_percent: float, mode: Mode = "auto") -> dict:
        """Line/stroke shade 0–100. Cast to int for Scripter."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineShade", round(shade_percent), name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_fill_transparency(name: str, opacity: float, mode: Mode = "auto") -> dict:
        """Fill opacity 0.0–1.0. 1.0 = opaque, 0.0 = invisible."""
        if not 0.0 <= opacity <= 1.0:
            return {"ok": False, "error": "opacity must be in [0.0, 1.0]"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setFillTransparency", opacity, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_transparency(name: str, opacity: float, mode: Mode = "auto") -> dict:
        if not 0.0 <= opacity <= 1.0:
            return {"ok": False, "error": "opacity must be in [0.0, 1.0]"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineTransparency", opacity, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_width(name: str, width_pt: float, mode: Mode = "auto") -> dict:
        """Stroke width in points. 0 hides the stroke."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineWidth", width_pt, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_style(name: str, style: str = "solid", mode: Mode = "auto") -> dict:
        """style ∈ {solid, dash, dot, dashdot, dashdotdot}."""
        if style not in LINE_STYLES:
            return {"ok": False, "error": f"style must be one of {sorted(LINE_STYLES)}"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineStyle", LINE_STYLES[style], name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_cap(name: str, cap: str = "flat", mode: Mode = "auto") -> dict:
        """Line end cap ∈ {flat, round, square}."""
        if cap not in LINE_CAPS:
            return {"ok": False, "error": f"cap must be one of {sorted(LINE_CAPS)}"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineCap", LINE_CAPS[cap], name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_line_join(name: str, join: str = "miter", mode: Mode = "auto") -> dict:
        """Corner join ∈ {miter, round, bevel}."""
        if join not in LINE_JOINS:
            return {"ok": False, "error": f"join must be one of {sorted(LINE_JOINS)}"}
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLineJoin", LINE_JOINS[join], name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_corner_radius(name: str, radius_pt: float, mode: Mode = "auto") -> dict:
        """Corner radius for rectangles, in points. Scribus stores it as int,
        so fractional values are rounded. 0 = sharp corners."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setCornerRadius", round(radius_pt), name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_fill_color(name: str, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("getFillColor", name)
        return {"ok": result.ok, "color": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_line_color(name: str, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("getLineColor", name)
        return {"ok": result.ok, "color": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_line_width(name: str, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("getLineWidth", name)
        return {"ok": result.ok, "width_pt": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def get_corner_radius(name: str, mode: Mode = "auto") -> dict:
        """Read the corner radius (in points) of a rectangle. Scribus
        stores corner radius as an integer point value."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("getCornerRadius", name)
        return {"ok": result.ok, "radius_pt": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def apply_gradient(
        name: str,
        type: str = "horizontal",
        color1: str = "Black",
        color2: str = "White",
        shade1: int = 100,
        shade2: int = 100,
        mode: Mode = "auto",
    ) -> dict:
        """Apply a two-stop gradient fill to the named object.

        ``type`` ∈ {none, horizontal, vertical, diagonal, cross_diagonal,
        radial}. ``color1`` / ``color2`` must be defined color names in
        the document. ``shade1`` / ``shade2`` are 0–100 (tint per stop).

        Use ``type='none'`` to clear the gradient (the object falls back
        to its plain fill color). For multi-stop or freeform gradients,
        Scribus's Scripter API only exposes two stops; build them
        manually via the Scribus UI and import the resulting .sla.

        **Radial caveat**: Scribus 1.7's ``setGradientFill`` anchors the
        radial gradient at the object's bbox corner by default — the
        inner color sits in the corner, not the center. Centering the
        gradient requires ``setGradientVector``, but its signature in
        1.7 takes 8+ numeric args (start, end, focal, scale, skew) that
        we don't yet wrap. To get a centered radial today, design the
        object in the Scribus UI and load its .sla, or use a horizontal
        / vertical / diagonal gradient in place of radial.
        """
        if type not in GRADIENT_TYPES:
            return {
                "ok": False,
                "error": f"type must be one of {sorted(GRADIENT_TYPES)}",
            }
        backend = await get_backend(ctx, mode)
        result = await backend.call(
            "setGradientFill",
            GRADIENT_TYPES[type],
            color1,
            int(shade1),
            color2,
            int(shade2),
            name,
        )
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def clear_gradient(name: str, mode: Mode = "auto") -> dict:
        """Remove any gradient fill from the named object (sets type=FILL_NOG).
        The object reverts to its plain fill color."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("setGradientFill", 0, "Black", 100, "White", 100, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

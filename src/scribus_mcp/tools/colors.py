from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.palette import (
    ROLE_NAMES,
    add_known_color,
    invalidate_palette,
)


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def define_color_cmyk(
        name: str,
        cyan: float,
        magenta: float,
        yellow: float,
        key: float,
        mode: Mode = "auto",
    ) -> dict:
        """Define a CMYK color. Each component 0–100 (float).

        Pick ``name`` as a semantic role (``"primary"``, ``"accent"``,
        ``"surface"``, ``"ink"``, ``"muted"``, ``"warning"``,
        ``"success"``, ``"subtle"``) so every later tool defaults to it
        without restating the color on every call. Any other name is
        accepted (the document palette is just a name → swatch map);
        only the canonical role names plug into the auto-defaulting.
        """
        if not name:
            return {"ok": False, "error": "name must not be empty"}
        for cname, cval in (("cyan", cyan), ("magenta", magenta), ("yellow", yellow), ("key", key)):
            if not 0.0 <= cval <= 100.0:
                return {
                    "ok": False,
                    "error": f"{cname} must be in [0, 100], got {cval}",
                }
        backend = await get_backend(ctx, mode)
        result = await backend.call("defineColorCMYKFloat", name, cyan, magenta, yellow, key)
        if result.ok:
            add_known_color(backend, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def define_color_rgb(
        name: str,
        red: int,
        green: int,
        blue: int,
        mode: Mode = "auto",
    ) -> dict:
        """Define an RGB color. Each component 0–255.

        Pick ``name`` as a semantic role (``"primary"``, ``"accent"``,
        ``"surface"``, ``"ink"``, ``"muted"``, ``"warning"``,
        ``"success"``, ``"subtle"``) so every later tool defaults to it
        without restating the color on every call. Any other name is
        accepted (the document palette is just a name → swatch map);
        only the canonical role names plug into the auto-defaulting.
        """
        if not name:
            return {"ok": False, "error": "name must not be empty"}
        for cname, cval in (("red", red), ("green", green), ("blue", blue)):
            if not 0 <= cval <= 255:
                return {
                    "ok": False,
                    "error": f"{cname} must be in [0, 255], got {cval}",
                }
        backend = await get_backend(ctx, mode)
        result = await backend.call("defineColorRGB", name, red, green, blue)
        if result.ok:
            add_known_color(backend, name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def list_colors(mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("getColorNames")
        return {"ok": result.ok, "colors": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def list_palette_roles() -> dict:
        """List the canonical palette role names recognised by tool defaults.

        Define any of these via ``define_color_rgb`` / ``define_color_cmyk``
        and every tool with a matching color slot will pick the role color
        automatically. Roles you don't define fall back to the historical
        ``"Black"`` default with the tool's conventional shade.
        """
        return {
            "ok": True,
            "roles": sorted(ROLE_NAMES),
            "error": None,
        }

    @mcp.tool()
    async def delete_color(name: str, replace_with: str = "None", mode: Mode = "auto") -> dict:
        """Delete a color and replace existing uses with `replace_with` (default 'None')."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("deleteColor", name, replace_with)
        if result.ok:
            invalidate_palette(backend)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

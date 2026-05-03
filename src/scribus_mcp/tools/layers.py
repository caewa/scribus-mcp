from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_layer(name: str, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("createLayer", name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def delete_layer(name: str, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("deleteLayer", name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def list_layers(mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("getLayers")
        return {"ok": result.ok, "layers": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_active_layer(name: str, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("setActiveLayer", name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def send_to_layer(object_name: str, layer_name: str, mode: Mode = "auto") -> dict:
        """Move ``object_name`` onto ``layer_name``. Mirrors the Scripter
        function ``sendToLayer`` — name kept consistent with the underlying
        Scribus API."""
        backend = await get_backend(ctx, mode)
        result = await backend.call("sendToLayer", layer_name, object_name)
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_layer_visible(name: str, visible: bool = True, mode: Mode = "auto") -> dict:
        # Some Scribus 1.6 builds expected an int for the flag; 1.7 takes
        # bool fine. Defensive cast is cheap and matches the int-cast
        # pattern used elsewhere (setFillShade, setCornerRadius, etc).
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLayerVisible", name, int(bool(visible)))
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def set_layer_printable(name: str, printable: bool = True, mode: Mode = "auto") -> dict:
        backend = await get_backend(ctx, mode)
        result = await backend.call("setLayerPrintable", name, int(bool(printable)))
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    if not ctx.config.run_script_enabled:
        return  # tool not registered when escape hatch is disabled

    @mcp.tool()
    async def run_script(
        body: str,
        result_expr: str = "None",
        mode: Mode = "auto",
    ) -> dict:
        """Run arbitrary Python inside Scribus's Scripter interpreter.

        Body has access to the `scribus` module. Returns the value of `result_expr`.

        DANGER: This is a full code-execution surface. Only enabled when the
        SCRIBUS_MCP_RUN_SCRIPT=1 env var is set on the server. In production
        runs (CI, shared deployments), keep it disabled and add purpose-built
        tools instead.
        """
        backend = await get_backend(ctx, mode)
        result = await backend.script(body, result_expr=result_expr)
        return {
            "ok": result.ok,
            "value": result.unwrap_or(),
            "error": result.error,
            "traceback": result.traceback,
        }

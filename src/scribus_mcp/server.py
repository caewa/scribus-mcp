from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from scribus_mcp.backends import HeadlessBackend, InteractiveBackend
from scribus_mcp.config import Config
from scribus_mcp.prompts import register_all as register_prompts
from scribus_mcp.resources import register_all as register_resources
from scribus_mcp.tools import register_all as register_tools
from scribus_mcp.tools._common import ServerCtx

log = logging.getLogger("scribus_mcp")


def build_server(config: Config | None = None) -> FastMCP:
    cfg = config or Config.from_env()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mcp = FastMCP(
        name="scribus-mcp",
        instructions=(
            "Scribus desktop publishing MCP. Tools manipulate Scribus documents via the "
            "Scripter Python API. Use mode='auto' (default) to let the server pick between "
            "an open Scribus session (interactive) and a fresh headless invocation. "
            "Coordinates are in millimeters unless documented otherwise."
        ),
    )

    headless = HeadlessBackend(cfg)
    interactive = InteractiveBackend(cfg)
    ctx = ServerCtx(config=cfg, headless=headless, interactive=interactive)

    register_tools(mcp, ctx)
    register_resources(mcp, ctx)
    register_prompts(mcp, ctx)

    log.info(
        "scribus-mcp ready (scribus_bin=%s, run_script_enabled=%s, runtime_dir=%s)",
        cfg.scribus_bin,
        cfg.run_script_enabled,
        cfg.runtime_dir,
    )
    return mcp

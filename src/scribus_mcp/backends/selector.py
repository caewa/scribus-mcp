from __future__ import annotations

from typing import Literal

from scribus_mcp.backends._launcher import ensure_bridge_running
from scribus_mcp.backends.base import BackendError, ScribusBackend
from scribus_mcp.backends.headless import HeadlessBackend
from scribus_mcp.backends.interactive import InteractiveBackend
from scribus_mcp.config import Config

Mode = Literal["auto", "headless", "interactive"]


async def pick_backend(
    mode: Mode,
    config: Config,
    headless: HeadlessBackend,
    interactive: InteractiveBackend,
) -> ScribusBackend:
    if mode == "headless":
        return headless
    if mode == "interactive":
        if not await interactive.is_available():
            ok, reason = await ensure_bridge_running(config, interactive)
            if not ok:
                raise BackendError(
                    "Interactive backend not available — "
                    f"{reason or 'no bridge is running'}. "
                    "Start Scribus and load scribus_mcp_bridge.spy from the Script menu, "
                    "or call this tool with mode='headless' / mode='auto'."
                )
        return interactive
    if await interactive.is_available():
        return interactive
    return headless

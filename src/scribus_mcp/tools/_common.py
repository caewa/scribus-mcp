from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scribus_mcp.backends import HeadlessBackend, InteractiveBackend, pick_backend
from scribus_mcp.backends.base import BackendError, ScribusBackend
from scribus_mcp.config import Config

Mode = Literal["auto", "headless", "interactive"]


@dataclass
class ServerCtx:
    config: Config
    headless: HeadlessBackend
    interactive: InteractiveBackend


async def get_backend(ctx: ServerCtx, mode: Mode) -> ScribusBackend:
    return await pick_backend(mode, ctx.config, ctx.headless, ctx.interactive)


__all__ = ["BackendError", "Mode", "ServerCtx", "get_backend"]

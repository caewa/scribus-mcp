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


# --- Scribus runtime version gating ----------------------------------------
# Some Scripter functions (``createBarcode``, …) only exist on Scribus 1.7+.
# A bare attribute lookup gives the user a cryptic
# ``module 'scribus' has no attribute 'createBarcode'`` — instead we probe
# ``scribus.scribus_version_info`` once per backend instance and return a
# structured ``ok=False`` payload telling the MCP client which feature it
# is, what version is required, and what version the running Scribus
# actually reports.

_VERSION_CACHE: dict[int, tuple[int, int, int]] = {}


async def get_scribus_version(backend: ScribusBackend) -> tuple[int, int, int]:
    """Return the running Scribus's ``(major, minor, patch)``.

    Cached per backend instance via ``id(backend)``. Returns ``(0, 0, 0)``
    if the probe fails (bridge unreachable, attribute missing, …) so
    callers can treat "unknown" as "fail closed for gated features".
    """
    key = id(backend)
    cached = _VERSION_CACHE.get(key)
    if cached is not None:
        return cached
    body = (
        "import scribus as _s\n"
        "_value = list(getattr(_s, 'scribus_version_info', (0, 0, 0))[:3])\n"
    )
    try:
        res = await backend.script(body, result_expr="_value")
    except Exception:
        return (0, 0, 0)
    if not res.ok or not isinstance(res.value, list) or len(res.value) < 3:
        return (0, 0, 0)
    try:
        version = (int(res.value[0]), int(res.value[1]), int(res.value[2]))
    except (TypeError, ValueError):
        return (0, 0, 0)
    _VERSION_CACHE[key] = version
    return version


async def require_min_scribus_version(
    backend: ScribusBackend,
    *,
    feature: str,
    required: tuple[int, int, int],
) -> dict | None:
    """Gate a tool call on the running Scribus's reported version.

    Returns ``None`` when the backend reports >= ``required``. Otherwise
    returns a tool-shaped ``ok=False`` payload with ``required_version``
    and ``actual_version`` fields so the MCP client can surface a clean
    "upgrade Scribus" message instead of an attribute-missing traceback.
    """
    actual = await get_scribus_version(backend)
    if actual >= required:
        return None
    req_str = ".".join(str(n) for n in required)
    act_str = (
        ".".join(str(n) for n in actual) if actual != (0, 0, 0) else "unknown"
    )
    return {
        "ok": False,
        "error": (
            f"{feature} requires Scribus {req_str}+ "
            f"(this Scribus reports {act_str}). "
            "Install / point SCRIBUS_BIN at a 1.7.x build — "
            "see README 'Scribus version requirements per feature'."
        ),
        "required_version": req_str,
        "actual_version": act_str,
    }


__all__ = [
    "BackendError",
    "Mode",
    "ServerCtx",
    "get_backend",
    "get_scribus_version",
    "require_min_scribus_version",
]

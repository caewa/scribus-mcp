from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Literal

from scribus_mcp.backends import HeadlessBackend, InteractiveBackend, pick_backend
from scribus_mcp.backends.base import BackendError, ScribusBackend
from scribus_mcp.config import Config

Mode = Literal["auto", "headless", "interactive"]


def clean_user_text(s: str) -> str:
    """Decode HTML/XML entities in user-supplied text before it hits Scribus.

    LLM clients sometimes "helpfully" pre-encode `&` as `&amp;`,
    `<` as `&lt;`, etc. — pattern-matching on training data where text
    was destined for HTML. Scribus's ``setText`` takes raw strings;
    Scribus then writes the SLA (an XML format) and re-escapes ``&``
    to ``&amp;`` itself, so the LLM's pre-encode produces ``&amp;amp;``
    on disk, which renders as the literal characters ``&amp;`` in the
    PDF. Defensive single-pass unescape at the MCP boundary undoes the
    LLM's mistake without touching anything that wasn't already
    encoded.

    ``html.unescape`` handles named entities (``&amp;``, ``&lt;``,
    ``&gt;``, ``&quot;``, ``&apos;``, case-insensitive), numeric
    entities (``&#x26;``, ``&#38;``), and is a single pass — so an
    intentional ``&amp;amp;`` becomes ``&amp;`` (one level of escape
    survives, as the LLM presumably intended one to render as
    literal text). Bare ``&`` is left alone.

    Skip this for content that legitimately contains literal entity
    references — e.g., source code passed to ``create_code_sample``.
    """
    if not s:
        return s
    return html.unescape(s)


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
    "clean_user_text",
    "get_backend",
    "get_scribus_version",
    "probe_scribus_version",
    "require_min_scribus_version",
]


# Public alias so tool registrations can import the probe under a name
# that doesn't shadow the user-facing ``get_scribus_version`` MCP tool.
probe_scribus_version = get_scribus_version

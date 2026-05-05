from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from scribus_mcp.backends.interactive import InteractiveBackend
from scribus_mcp.bridge import bridge_path
from scribus_mcp.config import Config

log = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"\b(\d+)\.(\d+)(?:\.\d+)?\b")


def _resolve_scribus_bin(scribus_bin: str) -> Path | None:
    """Return an existing path for ``scribus_bin`` or ``None``.

    Accepts both absolute paths and bare command names (``"scribus"``),
    resolving the latter via ``$PATH`` so the launcher matches the headless
    backend's lookup behavior.
    """
    p = Path(scribus_bin)
    if p.is_absolute() or p.exists():
        return p if p.exists() else None
    found = shutil.which(scribus_bin)
    return Path(found) if found else None


@lru_cache(maxsize=8)
def _detect_scribus_version(scribus_bin: str) -> tuple[int, int] | None:
    """Probe ``<scribus_bin> -v`` and return ``(major, minor)`` or ``None``.

    Cached per binary path. Output is localized (``"Scribus Version 1.7.3"``
    vs. ``"Version de Scribus 1.6.3"``), so we just regex the first
    ``MAJOR.MINOR`` number on stdout. Returns ``None`` if the probe fails or
    no version-shaped token is found.
    """
    try:
        result = subprocess.run(
            [scribus_bin, "-v"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError) as exc:
        # ValueError catches the case where subprocess.Popen has been
        # mocked by a test harness — the launcher tests stub it out and
        # we don't want a version probe to bring them down.
        log.debug("scribus -v probe failed: %s", exc)
        return None
    blob = (result.stdout or "") + "\n" + (result.stderr or "")
    match = _VERSION_RE.search(blob)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _scribus_already_running(scribus_bin: str) -> bool:
    """Best-effort: does an OS process matching the Scribus binary exist?

    Returns False on detection failure (timeout / missing tool) so the
    caller proceeds with spawn rather than blocking. We only use this to
    detect "Scribus open *without* the bridge" — false negatives just
    mean a duplicate window in that edge case, never a hang.
    """
    proc_name = Path(scribus_bin).name  # scribus.exe / scribus / Scribus
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/NH"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return proc_name.lower() in out.stdout.lower()
        # Match the exact process name (``/proc/PID/comm``), not the full
        # command line: ``-f`` would also match anything with ``scribus``
        # in its argv — including pytest invocations from a checkout
        # path like ``.../scribus-mcp/...`` — and trip the dup guard.
        result = subprocess.run(
            ["pgrep", "-x", proc_name],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


async def ensure_bridge_running(
    config: Config,
    interactive: InteractiveBackend,
    timeout_s: float = 20.0,
    poll_interval_s: float = 0.5,
) -> tuple[bool, str | None]:
    """Make sure an interactive bridge is reachable, launching Scribus if not.

    Returns ``(True, None)`` on success or ``(False, reason)`` if the bridge
    didn't come up in ``timeout_s``. Idempotent: if a bridge is already
    reachable, returns immediately without spawning anything.

    If a Scribus process is detected *without* a responding bridge, returns
    a clean error instead of spawning a duplicate window — the user should
    load the bridge into the existing instance via Script > Execute Script.
    """
    if await interactive.is_available():
        return True, None

    spy = bridge_path()
    if not spy.is_file():
        return False, f"bridge .spy not found at {spy}"

    # ``ignore_host_scribus`` skips every host-binary lookup so the
    # AppImage path always wins — the typical use case is a host with
    # Scribus 1.6 installed where the user wants the 1.7.x AppImage for
    # the full feature surface.
    if config.ignore_host_scribus:
        scribus_bin = None
        log.info(
            "SCRIBUS_MCP_IGNORE_HOST_SCRIBUS=1 — skipping host binary "
            "lookup, going straight to AppImage path."
        )
    else:
        scribus_bin = _resolve_scribus_bin(config.scribus_bin)
    if scribus_bin is None and config.auto_appimage:
        # Opt-in: fetch the official AppImage and use it. Runs the
        # blocking download on a worker thread so the asyncio loop
        # isn't pinned for the duration.
        from scribus_mcp.appimage import AppImageError, fetch_appimage_from_env

        try:
            scribus_bin = await asyncio.to_thread(
                fetch_appimage_from_env, log_fn=log.info
            )
        except AppImageError as exc:
            return False, f"SCRIBUS_MCP_AUTO_APPIMAGE fetch failed: {exc}"
    if scribus_bin is None:
        if config.ignore_host_scribus and not config.auto_appimage:
            return False, (
                "SCRIBUS_MCP_IGNORE_HOST_SCRIBUS=1 is set but "
                "SCRIBUS_MCP_AUTO_APPIMAGE isn't — nothing to launch. "
                "Set SCRIBUS_MCP_AUTO_APPIMAGE=1 (Linux) or unset "
                "IGNORE_HOST_SCRIBUS to fall back to the host binary."
            )
        return False, (
            f"Scribus binary not found at {config.scribus_bin!r}. "
            "Set SCRIBUS_BIN env var, install Scribus 1.6 / 1.7, or "
            "set SCRIBUS_MCP_AUTO_APPIMAGE=1 to auto-fetch the AppImage "
            "(Linux only)."
        )

    if _scribus_already_running(config.scribus_bin):
        return False, (
            "Scribus appears to be running but the bridge isn't responding. "
            "Open Script > Execute Script... and load "
            f"{spy} (or close that Scribus instance and retry to auto-launch)."
        )

    # ``-cl`` (console-only) is a Scribus 1.7+ flag; on 1.6 it's parsed as
    # a filename to open, which silently breaks ``-py`` execution. Probe
    # the binary and only emit the flag when we know it's supported.
    cmd = [str(scribus_bin), "-ns"]
    version = _detect_scribus_version(str(scribus_bin))
    if version is not None and version >= (1, 7):
        cmd.append("-cl")
    cmd += ["-py", str(spy)]
    log.info("Auto-launching Scribus %s + bridge: %s", version, cmd)

    try:
        kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **kwargs)
    except (OSError, FileNotFoundError) as exc:
        return False, f"failed to spawn Scribus: {exc}"

    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(poll_interval_s)
        if await interactive.is_available():
            log.info("Bridge came up after auto-launch")
            return True, None

    return False, (
        f"Scribus launched but bridge didn't register within {timeout_s:.0f}s. "
        "Check if Scribus opened a dialog or hit a Python error loading the bridge."
    )

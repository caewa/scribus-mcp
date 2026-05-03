from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from scribus_mcp.backends.interactive import InteractiveBackend
from scribus_mcp.bridge import bridge_path
from scribus_mcp.config import Config

log = logging.getLogger(__name__)


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
        result = subprocess.run(
            ["pgrep", "-f", proc_name],
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

    scribus_bin = Path(config.scribus_bin)
    if not scribus_bin.exists():
        return False, (
            f"Scribus binary not found at {config.scribus_bin!r}. "
            "Set SCRIBUS_BIN env var or install Scribus 1.7."
        )

    if _scribus_already_running(config.scribus_bin):
        return False, (
            "Scribus appears to be running but the bridge isn't responding. "
            "Open Script > Execute Script... and load "
            f"{spy} (or close that Scribus instance and retry to auto-launch)."
        )

    cmd = [str(scribus_bin), "-ns", "-cl", "-py", str(spy)]
    log.info("Auto-launching Scribus + bridge: %s", cmd)

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

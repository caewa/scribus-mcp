"""Opt-in helper that downloads the official Scribus AppImage.

The MCP can run on Scribus 1.6 with a few features gated off (see
``tools/_common.require_min_scribus_version``). For users who want the
full surface without hand-installing 1.7.x, this module fetches the
canonical AppImage from SourceForge and drops it where
``config._default_scribus_bin`` already probes
(``~/Applications/Scribus*.AppImage``).

Two entry points:

- ``scribus-mcp --fetch-appimage`` — explicit one-shot install.
- ``SCRIBUS_MCP_AUTO_APPIMAGE=1`` — let the launcher fetch on first
  call when no Scribus binary is resolvable.

Upstream does not publish a SHA256 file alongside the AppImage (only
GPG-signed ``.asc`` for the source tarballs), so the default path
trusts TLS + a sanity size floor. If the user wants stronger
guarantees they can pin a hash via ``--appimage-sha256`` or
``SCRIBUS_MCP_APPIMAGE_SHA256``.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

log = logging.getLogger(__name__)


class AppImageError(RuntimeError):
    """Raised when fetching, verifying, or installing the AppImage fails."""


# Canonical SourceForge URL for the Scribus 1.7.x AppImage. Verified from
# https://sourceforge.net/projects/scribus/files/scribus-devel/ — the
# "scribus-devel" path serves the 1.7 development line; "scribus" serves
# the 1.6 stable line. We default to 1.7.3 since that's what unlocks the
# full tool surface (createBarcode, etc.). Override via env or CLI flag.
DEFAULT_APPIMAGE_VERSION = "1.7.3"
DEFAULT_APPIMAGE_URL = (
    "https://downloads.sourceforge.net/project/scribus/scribus-devel/"
    f"{DEFAULT_APPIMAGE_VERSION}/"
    f"scribus-{DEFAULT_APPIMAGE_VERSION}-linux-x86_64.AppImage"
)
# Sanity floor — Scribus 1.7.3 ships at ~138 MB; anything under 50 MB is
# certainly an HTML error page or a truncated download.
DEFAULT_MIN_SIZE_MB = 50


def default_install_dir() -> Path:
    """Match the path ``config._default_scribus_bin`` already probes."""
    return Path.home() / "Applications"


def install_target(version: str, install_dir: Path | None = None) -> Path:
    """Return the absolute path the AppImage will live at.

    Format ``Scribus-X.Y.Z-x86_64.AppImage`` matches the glob pattern
    ``config._default_scribus_bin`` walks (``Scribus*.AppImage``), so the
    auto-launcher picks it up automatically without any env var.
    """
    return (install_dir or default_install_dir()) / f"Scribus-{version}-x86_64.AppImage"


def _sha256_of(path: Path, *, chunk_size: int = 1 << 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_appimage(
    *,
    url: str | None = None,
    version: str = DEFAULT_APPIMAGE_VERSION,
    install_dir: Path | None = None,
    expected_sha256: str | None = None,
    min_size_mb: int = DEFAULT_MIN_SIZE_MB,
    log_fn: Callable[[str], None] | None = None,
) -> Path:
    """Download + install the Scribus AppImage. Idempotent.

    Returns the absolute path of the installed (or already-present)
    AppImage. Raises ``AppImageError`` on any failure (network, size
    floor, SHA256 mismatch).

    Idempotency rules:
      - If the target file exists and ``expected_sha256`` is given, the
        SHA is checked; mismatch → re-download.
      - If the target file exists and no SHA is given, it's accepted
        as-is (this is what ``SCRIBUS_MCP_AUTO_APPIMAGE`` relies on so
        repeated tool calls don't refetch 138 MB).
    """
    say = log_fn or log.info
    url = url or DEFAULT_APPIMAGE_URL
    target = install_target(version, install_dir)

    if target.exists():
        if expected_sha256:
            actual = _sha256_of(target)
            if actual == expected_sha256:
                say(f"AppImage already installed and SHA256 matches: {target}")
                return target
            say(
                f"AppImage at {target} has SHA256 {actual} but expected "
                f"{expected_sha256} — redownloading."
            )
            target.unlink()
        else:
            say(f"AppImage already present (no SHA pin to verify): {target}")
            return target

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / (target.name + ".part")
    if tmp.exists():
        tmp.unlink()

    say(f"Downloading {url}")
    say(f"  -> {target} (~140 MB, this can take a minute)")
    try:
        with urlopen(url) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out)
    except (URLError, OSError) as exc:
        if tmp.exists():
            tmp.unlink()
        raise AppImageError(f"Download failed: {exc}") from exc

    size_mb = tmp.stat().st_size / 1024 / 1024
    if size_mb < min_size_mb:
        tmp.unlink()
        raise AppImageError(
            f"Downloaded file is only {size_mb:.1f} MB "
            f"(expected >= {min_size_mb} MB). The URL probably served an "
            "error page instead of the AppImage."
        )

    if expected_sha256:
        actual = _sha256_of(tmp)
        if actual != expected_sha256:
            tmp.unlink()
            raise AppImageError(
                f"SHA256 mismatch: got {actual}, expected {expected_sha256}"
            )
        say(f"SHA256 verified: {actual}")

    tmp.rename(target)
    target.chmod(0o755)
    say(f"Installed: {target} ({size_mb:.1f} MB)")
    return target


def fetch_appimage_from_env(
    *,
    log_fn: Callable[[str], None] | None = None,
) -> Path:
    """Convenience wrapper that pulls overrides from env vars.

    Env vars consumed:

    - ``SCRIBUS_MCP_APPIMAGE_URL`` — full download URL.
    - ``SCRIBUS_MCP_APPIMAGE_VERSION`` — version tag used in the
      installed filename (and in the default URL if no URL override).
    - ``SCRIBUS_MCP_APPIMAGE_SHA256`` — pin a SHA256 to verify against.
    - ``SCRIBUS_MCP_APPIMAGE_INSTALL_DIR`` — override
      ``~/Applications`` as the install location.
    """
    install_dir_env = os.environ.get("SCRIBUS_MCP_APPIMAGE_INSTALL_DIR")
    return fetch_appimage(
        url=os.environ.get("SCRIBUS_MCP_APPIMAGE_URL"),
        version=os.environ.get("SCRIBUS_MCP_APPIMAGE_VERSION", DEFAULT_APPIMAGE_VERSION),
        install_dir=Path(install_dir_env) if install_dir_env else None,
        expected_sha256=os.environ.get("SCRIBUS_MCP_APPIMAGE_SHA256") or None,
        log_fn=log_fn,
    )


__all__ = [
    "DEFAULT_APPIMAGE_URL",
    "DEFAULT_APPIMAGE_VERSION",
    "DEFAULT_MIN_SIZE_MB",
    "AppImageError",
    "default_install_dir",
    "fetch_appimage",
    "fetch_appimage_from_env",
    "install_target",
]

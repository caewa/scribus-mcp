from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _runtime_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "scribus-mcp"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "scribus-mcp"
    base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp"
    return Path(base) / "scribus-mcp"


def _default_scribus_bin() -> str:
    if sys.platform == "win32":
        for candidate in (
            r"C:\Program Files\Scribus 1.7.3\scribus.exe",
            r"C:\Program Files\Scribus 1.7\scribus.exe",
            r"C:\Program Files\Scribus 1.6\scribus.exe",
        ):
            if Path(candidate).exists():
                return candidate
        return "scribus.exe"
    if sys.platform == "darwin":
        for candidate in ("/Applications/Scribus.app/Contents/MacOS/Scribus",):
            if Path(candidate).exists():
                return candidate
        return "scribus"
    # Linux / *bsd: prefer ``scribus`` on PATH; otherwise probe a few
    # well-known AppImage drop locations.
    home = Path.home()
    for candidate in (
        home / ".local" / "bin" / "scribus",
        Path("/usr/local/bin/scribus"),
    ):
        if candidate.exists():
            return str(candidate)
    # AppImage glob — pick the newest-by-mtime if multiple are present.
    appimage_locations = [home / "Applications", home / "Downloads", Path("/opt")]
    candidates: list[Path] = []
    for d in appimage_locations:
        if d.is_dir():
            candidates.extend(d.glob("Scribus*.AppImage"))
            candidates.extend(d.glob("scribus*.AppImage"))
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return str(candidates[0])
    return "scribus"


@dataclass(frozen=True)
class Config:
    scribus_bin: str
    runtime_dir: Path
    workdir: Path
    discovery_file: Path
    run_script_enabled: bool
    log_level: str
    use_xvfb: bool
    # Extra directories the headless backend should add to Scribus's
    # ExtraFontDirs before spawning. Empty by default; set via env var
    # SCRIBUS_MCP_EXTRA_FONT_PATHS as os.pathsep-separated list.
    # Each per-job spawn will get a fresh temporary prefs dir with these
    # paths registered, then `-pr <tmpdir>` is passed to Scribus.
    extra_font_paths: tuple[str, ...] = ()
    # Opt-in: when no Scribus binary can be resolved at launch time,
    # fetch the official AppImage from SourceForge (Linux only — see
    # scribus_mcp/appimage.py). Off by default since it pulls ~140 MB
    # over the network.
    auto_appimage: bool = False

    @classmethod
    def from_env(cls) -> Config:
        runtime = _runtime_dir()
        runtime.mkdir(parents=True, exist_ok=True)
        workdir = runtime / "jobs"
        workdir.mkdir(parents=True, exist_ok=True)
        raw_paths = os.environ.get("SCRIBUS_MCP_EXTRA_FONT_PATHS", "")
        extra = tuple(p for p in raw_paths.split(os.pathsep) if p) if raw_paths else ()
        return cls(
            scribus_bin=os.environ.get("SCRIBUS_BIN") or _default_scribus_bin(),
            runtime_dir=runtime,
            workdir=workdir,
            discovery_file=runtime / "scribus-mcp.json",
            run_script_enabled=os.environ.get("SCRIBUS_MCP_RUN_SCRIPT", "0") == "1",
            log_level=os.environ.get("SCRIBUS_MCP_LOG_LEVEL", "INFO").upper(),
            use_xvfb=os.environ.get("SCRIBUS_MCP_USE_XVFB", "0") == "1",
            extra_font_paths=extra,
            auto_appimage=os.environ.get("SCRIBUS_MCP_AUTO_APPIMAGE", "0") == "1",
        )


def read_discovery(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None

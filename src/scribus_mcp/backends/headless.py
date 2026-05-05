from __future__ import annotations

import asyncio
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from scribus_mcp.backends.base import BackendError, ScribusBackend, ScribusResult
from scribus_mcp.config import Config
from scribus_mcp.scripter_template import py_call, render_headless_script


def _write_prefs_with_font_dirs(prefs_dir: Path, font_dirs: tuple[str, ...]) -> Path:
    """Write a minimal Scribus prefs XML pre-populated with ExtraFontDirs.

    Scribus fills in defaults for any keys we don't set, so we only need
    the ``Fonts/ExtraFontDirs`` subtree. Returns the path to the written
    XML so the caller can log it.
    """
    prefs_dir.mkdir(parents=True, exist_ok=True)
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<preferences>",
        '  <level name="application">',
        '    <context name="Fonts">',
        '      <table name="ExtraFontDirs">',
    ]
    for d in font_dirs:
        # Resolve to absolute, normalize, and XML-escape minimally
        norm = str(Path(d).expanduser().resolve()).replace("&", "&amp;").replace("<", "&lt;")
        xml_lines.append(f"        <row><col>{norm}</col></row>")
    xml_lines.extend(
        [
            "      </table>",
            "    </context>",
            "  </level>",
            "</preferences>",
        ]
    )
    target = prefs_dir / "prefs172.xml"
    target.write_text("\n".join(xml_lines) + "\n", encoding="utf-8")
    return target


class HeadlessBackend(ScribusBackend):
    """Spawns `scribus -g -py <script>` per call. Stateless across calls.

    Multi-step jobs should chain operations into one `script()` body and
    save/load the .sla in between if persistence is needed.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    async def is_available(self) -> bool:
        # Honor IGNORE_HOST_SCRIBUS / AUTO_APPIMAGE — same resolver the
        # launcher uses, so headless and interactive agree on the binary.
        from scribus_mcp.backends._launcher import resolve_scribus_binary

        return await resolve_scribus_binary(self.config) is not None

    async def call(self, method: str, *args: Any, **kwargs: Any) -> ScribusResult:
        body = f"_value = {py_call(method, *args, **kwargs)}"
        return await self.script(body, result_expr="_value")

    async def script(self, body: str, result_expr: str = "None") -> ScribusResult:
        job_id = uuid.uuid4().hex
        script_path = self.config.workdir / f"job-{job_id}.py"
        result_path = self.config.workdir / f"job-{job_id}.json"

        script_path.write_text(
            render_headless_script(body, result_expr, str(result_path)),
            encoding="utf-8",
        )

        prefs_dir: Path | None = None
        if self.config.extra_font_paths:
            prefs_dir = self.config.workdir / f"prefs-{job_id}"
            _write_prefs_with_font_dirs(prefs_dir, self.config.extra_font_paths)

        # Resolve once per call (cached after the first lookup) so
        # IGNORE_HOST_SCRIBUS / AUTO_APPIMAGE are honored. Falls back to
        # config.scribus_bin if the resolver returns None — preserves the
        # historical "binary not found" error path below.
        from scribus_mcp.backends._launcher import resolve_scribus_binary

        resolved = await resolve_scribus_binary(self.config)
        scribus_bin = str(resolved) if resolved is not None else self.config.scribus_bin
        cmd = self._build_cmd(script_path, prefs_dir, scribus_bin=scribus_bin)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
        except FileNotFoundError as exc:
            raise BackendError(
                f"Scribus binary not found at {self.config.scribus_bin!r}. "
                f"Set SCRIBUS_BIN env var to override."
            ) from exc
        finally:
            script_path.unlink(missing_ok=True)
            if prefs_dir is not None:
                shutil.rmtree(prefs_dir, ignore_errors=True)

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")

        if not result_path.exists():
            result_path.unlink(missing_ok=True)
            return ScribusResult(
                ok=False,
                error=f"Scribus exited (rc={proc.returncode}) without producing a result",
                stdout=stdout,
                stderr=stderr,
            )

        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        finally:
            result_path.unlink(missing_ok=True)

        return ScribusResult(
            ok=bool(payload.get("ok")),
            value=payload.get("value"),
            error=payload.get("error"),
            traceback=payload.get("traceback"),
            stdout=stdout,
            stderr=stderr,
        )

    def _build_cmd(
        self,
        script_path: Path,
        prefs_dir: Path | None = None,
        scribus_bin: str | None = None,
    ) -> list[str]:
        # ``scribus_bin`` overrides ``config.scribus_bin`` when the caller
        # has already resolved the binary (e.g. via the AppImage path).
        # Tests still call this without the override and get the legacy
        # config-driven path.
        if scribus_bin is None:
            scribus_bin = self.config.scribus_bin
        # Scribus headless: -g (no GUI), -ns (no splash). -pr <dir> overrides
        # the per-user prefs directory — we use this when extra_font_paths
        # is configured, so the spawned Scribus picks up additional font
        # directories without polluting the user's persistent prefs.
        # -py <script> must come last (per Scribus help).
        base = [scribus_bin, "-g", "-ns"]
        if prefs_dir is not None:
            base.extend(["-pr", str(prefs_dir)])
        base.extend(["-py", str(script_path)])
        if self.config.use_xvfb and sys.platform.startswith("linux"):
            return ["xvfb-run", "-a", *base]
        return base

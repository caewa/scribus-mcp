"""Auto-launch path for the interactive bridge.

We mock ``subprocess.Popen`` so the test never actually spawns Scribus.
The InteractiveBackend's ``is_available`` is also patched to drive the
poll loop in a controlled way.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from scribus_mcp.backends._launcher import (
    _detect_scribus_version,
    ensure_bridge_running,
)
from scribus_mcp.backends.interactive import InteractiveBackend
from scribus_mcp.config import Config


def _cfg(tmp_path: Path) -> Config:
    base = Config.from_env()
    return replace(
        base,
        runtime_dir=tmp_path,
        workdir=tmp_path / "jobs",
        discovery_file=tmp_path / "discovery.json",
    )


@pytest.fixture(autouse=True)
def _clear_binary_cache():
    """Drop the binary-resolver cache between tests.

    Cache is keyed by ``id(config)``; different tests build different
    Config dataclasses but Python may reuse the freed id, so without
    this an earlier test's resolved binary leaks into a later test.
    """
    from scribus_mcp.backends._launcher import _invalidate_binary_cache

    _invalidate_binary_cache()
    yield
    _invalidate_binary_cache()


@pytest.mark.asyncio
async def test_already_available_returns_without_spawn(tmp_path):
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=True),
        patch("subprocess.Popen") as popen,
    ):
        ok, reason = await ensure_bridge_running(cfg, inter, timeout_s=1.0)

    assert ok is True
    assert reason is None
    popen.assert_not_called()


@pytest.mark.asyncio
async def test_spawn_then_polls_and_succeeds(tmp_path):
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    avail_calls = {"n": 0}

    async def fake_avail():
        avail_calls["n"] += 1
        return avail_calls["n"] >= 2  # first call (preflight) False, second True

    with (
        patch.object(inter, "is_available", side_effect=fake_avail),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=False),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=(1, 7),
        ),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        # config.scribus_bin must point at something that exists for the
        # binary check to pass; reuse the test's own tmp_path.
        fake_bin = tmp_path / "scribus.exe"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        ok, reason = await ensure_bridge_running(
            cfg2, inter, timeout_s=2.0, poll_interval_s=0.1
        )

    assert ok is True
    assert reason is None
    popen.assert_called_once()
    args = popen.call_args.args[0]
    # The launcher used to emit ``-cl`` for 1.7+ thinking it was a
    # "console-only" flag, but 1.7.3 doesn't list it in --help (silently
    # ignored). Pin that we no longer emit it.
    assert "-cl" not in args
    assert "-ns" in args
    assert "-py" in args


@pytest.mark.asyncio
async def test_dup_window_guard_blocks_spawn(tmp_path):
    """If Scribus is already running but the bridge isn't, don't spawn a duplicate."""
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=True),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        fake_bin = tmp_path / "scribus.exe"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        ok, reason = await ensure_bridge_running(cfg2, inter, timeout_s=0.5)

    assert ok is False
    assert "appears to be running" in (reason or "")
    popen.assert_not_called()


@pytest.mark.asyncio
async def test_timeout_when_bridge_never_comes_up(tmp_path):
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=False),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=(1, 7),
        ),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        fake_bin = tmp_path / "scribus.exe"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        ok, reason = await ensure_bridge_running(
            cfg2, inter, timeout_s=0.3, poll_interval_s=0.1
        )

    assert ok is False
    assert "didn't register" in (reason or "")
    popen.assert_called_once()


@pytest.mark.asyncio
async def test_missing_scribus_binary_fails_cleanly(tmp_path):
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with patch.object(inter, "is_available", return_value=False):
        cfg2 = replace(cfg, scribus_bin=str(tmp_path / "nope.exe"))
        ok, reason = await ensure_bridge_running(cfg2, inter, timeout_s=0.5)

    assert ok is False
    assert "not found" in (reason or "")


@pytest.mark.asyncio
async def test_spawn_omits_cl_flag_on_scribus_16(tmp_path):
    """Scribus 1.6 doesn't accept ``-cl``; the launcher must not emit it."""
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=False),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=(1, 6),
        ),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        fake_bin = tmp_path / "scribus"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        await ensure_bridge_running(cfg2, inter, timeout_s=0.2, poll_interval_s=0.1)

    popen.assert_called_once()
    args = popen.call_args.args[0]
    assert "-cl" not in args
    assert "-py" in args
    assert "-ns" in args


@pytest.mark.asyncio
async def test_spawn_omits_cl_flag_on_scribus_17(tmp_path):
    """Regression: 1.7.3 doesn't list ``-cl`` in --help — it was being
    silently ignored. The launcher must no longer emit it for 1.7+."""
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=False),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=(1, 7),
        ),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        fake_bin = tmp_path / "scribus"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        await ensure_bridge_running(cfg2, inter, timeout_s=0.2, poll_interval_s=0.1)

    args = popen.call_args.args[0]
    assert "-cl" not in args


@pytest.mark.asyncio
async def test_spawn_sets_qt_qpa_platform_xcb_on_linux(tmp_path):
    """The AppImage's bundled Qt renders a black window under Wayland;
    forcing ``QT_QPA_PLATFORM=xcb`` via the spawn env is the well-known
    workaround. Pin that the launcher sets it on Linux."""
    if sys.platform == "win32":
        pytest.skip("env tweak is Linux-only")
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=False),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=(1, 7),
        ),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        fake_bin = tmp_path / "scribus"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        await ensure_bridge_running(cfg2, inter, timeout_s=0.2, poll_interval_s=0.1)

    env = popen.call_args.kwargs.get("env", {})
    assert env.get("QT_QPA_PLATFORM") == "xcb"


@pytest.mark.asyncio
async def test_spawn_qt_platform_respects_user_override(tmp_path):
    """If the user has already set QT_QPA_PLATFORM, the launcher must
    not stomp on their preference (``setdefault``, not ``=``)."""
    if sys.platform == "win32":
        pytest.skip("env tweak is Linux-only")
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    import os as _os

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=False),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=(1, 7),
        ),
        patch.dict(_os.environ, {"QT_QPA_PLATFORM": "wayland"}),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        fake_bin = tmp_path / "scribus"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        await ensure_bridge_running(cfg2, inter, timeout_s=0.2, poll_interval_s=0.1)

    env = popen.call_args.kwargs.get("env", {})
    assert env.get("QT_QPA_PLATFORM") == "wayland"  # user wins


@pytest.mark.asyncio
async def test_spawn_omits_cl_flag_when_version_unknown(tmp_path):
    """If ``-v`` probing fails we play it safe and skip ``-cl`` (1.6 default)."""
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
        patch("scribus_mcp.backends._launcher._scribus_already_running", return_value=False),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=None,
        ),
    ):
        spy = tmp_path / "fake.spy"
        spy.write_text("# noop")
        bp.return_value = spy
        fake_bin = tmp_path / "scribus"
        fake_bin.write_text("")
        cfg2 = replace(cfg, scribus_bin=str(fake_bin))
        await ensure_bridge_running(cfg2, inter, timeout_s=0.2, poll_interval_s=0.1)

    args = popen.call_args.args[0]
    assert "-cl" not in args


def test_detect_scribus_version_parses_localized_output(tmp_path):
    """Version probe must work across locales (en/fr at least)."""
    _detect_scribus_version.cache_clear()
    en_blob = "Scribus Version 1.7.3\n"
    fr_blob = "Version de Scribus 1.6.3\n"

    fake = type("R", (), {"stdout": en_blob, "stderr": ""})()
    with patch("subprocess.run", return_value=fake):
        assert _detect_scribus_version("/fake/scribus-en") == (1, 7)

    _detect_scribus_version.cache_clear()
    fake = type("R", (), {"stdout": fr_blob, "stderr": ""})()
    with patch("subprocess.run", return_value=fake):
        assert _detect_scribus_version("/fake/scribus-fr") == (1, 6)

    _detect_scribus_version.cache_clear()
    fake = type("R", (), {"stdout": "no numbers here", "stderr": ""})()
    with patch("subprocess.run", return_value=fake):
        assert _detect_scribus_version("/fake/scribus-broken") is None


@pytest.mark.asyncio
async def test_missing_bridge_spy_fails_cleanly(tmp_path):
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("scribus_mcp.backends._launcher.bridge_path") as bp,
    ):
        bp.return_value = tmp_path / "missing.spy"
        ok, reason = await ensure_bridge_running(cfg, inter, timeout_s=0.5)

    assert ok is False
    assert ".spy not found" in (reason or "")


# ----- ignore_host_scribus -------------------------------------------------


@pytest.mark.asyncio
async def test_ignore_host_skips_resolve_and_uses_appimage(tmp_path):
    """``ignore_host_scribus=True`` skips the host-binary lookup entirely
    and falls through to the AppImage path. Even when SCRIBUS_BIN points
    at a perfectly valid executable, the launcher must not use it."""
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    # A valid host binary that the launcher should NOT pick because the
    # ignore flag is set.
    host_bin = tmp_path / "scribus"
    host_bin.write_text("")
    # The fake AppImage path the worker thread will return.
    appimage_bin = tmp_path / "Scribus-1.7.3-x86_64.AppImage"
    appimage_bin.write_text("")

    spy = tmp_path / "fake.spy"
    spy.write_text("# noop")

    cfg2 = replace(
        cfg,
        scribus_bin=str(host_bin),
        auto_appimage=True,
        ignore_host_scribus=True,
    )

    with (
        patch.object(inter, "is_available", return_value=False),
        patch("subprocess.Popen") as popen,
        patch("scribus_mcp.backends._launcher.bridge_path", return_value=spy),
        patch(
            "scribus_mcp.backends._launcher._scribus_already_running",
            return_value=False,
        ),
        patch(
            "scribus_mcp.backends._launcher._resolve_scribus_bin"
        ) as resolve,
        patch(
            "scribus_mcp.appimage.fetch_appimage_from_env",
            return_value=appimage_bin,
        ),
        patch(
            "scribus_mcp.backends._launcher._detect_scribus_version",
            return_value=(1, 7),
        ),
    ):
        await ensure_bridge_running(cfg2, inter, timeout_s=0.2, poll_interval_s=0.1)

    # The host-binary resolver must NOT have been consulted.
    resolve.assert_not_called()
    popen.assert_called_once()
    cmd = popen.call_args.args[0]
    # Spawned with the AppImage path, not the host binary.
    assert cmd[0] == str(appimage_bin)


@pytest.mark.asyncio
async def test_ignore_host_without_auto_appimage_fails_cleanly(tmp_path):
    """``ignore_host_scribus=True`` + ``auto_appimage=False`` is a
    misconfiguration — host lookup is suppressed and there's no AppImage
    fallback. Surface a clear error instead of leaking the ambiguous
    "binary not found at ..." message."""
    cfg = _cfg(tmp_path)
    inter = InteractiveBackend(cfg)

    host_bin = tmp_path / "scribus"
    host_bin.write_text("")
    cfg2 = replace(
        cfg,
        scribus_bin=str(host_bin),
        ignore_host_scribus=True,
        auto_appimage=False,
    )

    with patch.object(inter, "is_available", return_value=False):
        ok, reason = await ensure_bridge_running(cfg2, inter, timeout_s=0.2)

    assert ok is False
    assert "IGNORE_HOST_SCRIBUS" in (reason or "")
    assert "AUTO_APPIMAGE" in (reason or "")


def test_config_reads_ignore_host_scribus_from_env(monkeypatch):
    monkeypatch.setenv("SCRIBUS_MCP_IGNORE_HOST_SCRIBUS", "1")
    cfg = Config.from_env()
    assert cfg.ignore_host_scribus is True

    monkeypatch.setenv("SCRIBUS_MCP_IGNORE_HOST_SCRIBUS", "0")
    cfg = Config.from_env()
    assert cfg.ignore_host_scribus is False

    monkeypatch.delenv("SCRIBUS_MCP_IGNORE_HOST_SCRIBUS", raising=False)
    cfg = Config.from_env()
    assert cfg.ignore_host_scribus is False


# ----- resolve_scribus_binary (shared by both backends) -------------------


@pytest.mark.asyncio
async def test_resolve_binary_skips_host_when_ignore_set(tmp_path):
    """``ignore_host_scribus=True`` skips host lookup entirely; the
    AppImage path returns. Regression: previously only the bridge
    launcher honored this — the headless backend kept using the host
    binary, so ``mode='auto'`` still saw 1.6.3 even when the user had
    asked for the AppImage."""
    from scribus_mcp.backends._launcher import (
        _invalidate_binary_cache,
        resolve_scribus_binary,
    )

    _invalidate_binary_cache()

    cfg = _cfg(tmp_path)
    host_bin = tmp_path / "scribus"
    host_bin.write_text("")
    appimage_bin = tmp_path / "Scribus-1.7.3-x86_64.AppImage"
    appimage_bin.write_text("")

    cfg2 = replace(
        cfg,
        scribus_bin=str(host_bin),
        ignore_host_scribus=True,
        auto_appimage=True,
    )

    with (
        patch(
            "scribus_mcp.backends._launcher._resolve_scribus_bin"
        ) as resolve,
        patch(
            "scribus_mcp.appimage.fetch_appimage_from_env",
            return_value=appimage_bin,
        ),
    ):
        result = await resolve_scribus_binary(cfg2)

    resolve.assert_not_called()
    assert result == appimage_bin
    _invalidate_binary_cache()


@pytest.mark.asyncio
async def test_resolve_binary_caches_per_config(tmp_path):
    """Repeated calls (e.g. one per headless tool spawn) must reuse the
    same resolved path — otherwise the AppImage gets re-downloaded on
    every call."""
    from scribus_mcp.backends._launcher import (
        _invalidate_binary_cache,
        resolve_scribus_binary,
    )

    _invalidate_binary_cache()

    cfg = _cfg(tmp_path)
    appimage_bin = tmp_path / "Scribus-1.7.3-x86_64.AppImage"
    appimage_bin.write_text("")
    cfg2 = replace(
        cfg,
        ignore_host_scribus=True,
        auto_appimage=True,
    )

    with patch(
        "scribus_mcp.appimage.fetch_appimage_from_env",
        return_value=appimage_bin,
    ) as fetch:
        a = await resolve_scribus_binary(cfg2)
        b = await resolve_scribus_binary(cfg2)
        c = await resolve_scribus_binary(cfg2)

    assert a == b == c == appimage_bin
    fetch.assert_called_once()
    _invalidate_binary_cache()


@pytest.mark.asyncio
async def test_headless_build_cmd_uses_resolved_binary(tmp_path):
    """The headless backend must spawn Scribus with the AppImage path
    when IGNORE_HOST_SCRIBUS is set, not the host binary on $PATH.
    Regression: ``mode='auto'`` returned 1.6.3 because headless ignored
    the env vars."""
    from scribus_mcp.backends._launcher import _invalidate_binary_cache
    from scribus_mcp.backends.headless import HeadlessBackend

    _invalidate_binary_cache()

    cfg = _cfg(tmp_path)
    host_bin = tmp_path / "scribus"
    host_bin.write_text("")
    appimage_bin = tmp_path / "Scribus-1.7.3-x86_64.AppImage"
    appimage_bin.write_text("")
    cfg2 = replace(
        cfg,
        scribus_bin=str(host_bin),
        ignore_host_scribus=True,
        auto_appimage=True,
    )

    cfg2.workdir.mkdir(parents=True, exist_ok=True)
    backend = HeadlessBackend(cfg2)

    # Trigger one script() call. We can't actually spawn Scribus, so
    # mock subprocess and inspect the cmd.
    class _FakeProc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    with (
        patch(
            "scribus_mcp.appimage.fetch_appimage_from_env",
            return_value=appimage_bin,
        ),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_FakeProc(),
        ) as spawn,
    ):
        # The script will fail to produce a result file (no real Scribus),
        # but we only care about the cmd that was built.
        await backend.script("_value = 1", result_expr="_value")

    cmd = spawn.call_args.args
    assert cmd[0] == str(appimage_bin), (
        f"headless used host {host_bin} instead of AppImage {appimage_bin}"
    )
    _invalidate_binary_cache()

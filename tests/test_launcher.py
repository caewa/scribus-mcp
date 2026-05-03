"""Auto-launch path for the interactive bridge.

We mock ``subprocess.Popen`` so the test never actually spawns Scribus.
The InteractiveBackend's ``is_available`` is also patched to drive the
poll loop in a controlled way.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from scribus_mcp.backends._launcher import ensure_bridge_running
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

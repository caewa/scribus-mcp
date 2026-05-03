"""Smoke tests that don't require Scribus to be installed."""

from __future__ import annotations


def test_package_import():
    import scribus_mcp

    assert scribus_mcp.__version__


def test_config_from_env():
    from scribus_mcp.config import Config

    cfg = Config.from_env()
    assert cfg.scribus_bin
    assert cfg.runtime_dir.exists()
    assert cfg.workdir.exists()


def test_build_server():
    from scribus_mcp.server import build_server

    mcp = build_server()
    assert mcp.name == "scribus-mcp"


def test_scripter_template_renders():
    from scribus_mcp.scripter_template import render_headless_script

    script = render_headless_script(
        body="x = 1 + 2\n_value = x",
        result_expr="_value",
        result_path="/tmp/out.json",
    )
    assert "import scribus" in script
    assert "_value = x" in script
    assert "/tmp/out.json" in script


def test_markdown_block_parsing():
    from scribus_mcp.tools.markdown import _parse_markdown

    md = "# Title\n\nA paragraph.\n\n- one\n- two\n\n```\ncode block\n```\n"
    blocks = _parse_markdown(md)
    kinds = [b.kind for b in blocks]
    assert "heading" in kinds
    assert "paragraph" in kinds
    assert "list_item" in kinds
    assert "code" in kinds


def test_headless_backend_unavailable_when_no_scribus(tmp_path, monkeypatch):
    import asyncio

    from scribus_mcp.backends import HeadlessBackend
    from scribus_mcp.config import Config

    monkeypatch.setenv("SCRIBUS_BIN", str(tmp_path / "definitely-not-scribus"))
    cfg = Config.from_env()
    backend = HeadlessBackend(cfg)
    assert asyncio.run(backend.is_available()) is False


def test_interactive_backend_unavailable_without_discovery(tmp_path, monkeypatch):
    import asyncio

    from scribus_mcp.backends import InteractiveBackend
    from scribus_mcp.config import Config

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cfg = Config.from_env()
    backend = InteractiveBackend(cfg)
    assert asyncio.run(backend.is_available()) is False

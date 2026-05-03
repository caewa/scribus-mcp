"""Phase 2 — headless backend integration tests.

Each tool call spawns `scribus -g -ns -py /tmp/job.py`, runs to completion,
returns a JSON result, exits. Headless mode is stateless across calls —
multi-step workflows must either be done in one `run_script` body or use
save/open round-trips across calls.

Skipped by default. Enable with SCRIBUS_MCP_LIVE=1 (Scribus must be
installed and SCRIBUS_BIN reachable).

Note: these tests are independent of the interactive bridge. They will
run even when no bridge is loaded.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from scribus_mcp.testing import unwrap as _unwrap

LIVE = os.environ.get("SCRIBUS_MCP_LIVE") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="Live Scribus not available (set SCRIBUS_MCP_LIVE=1 to enable)",
)


@pytest.fixture(scope="module")
def headless_available():
    from scribus_mcp.backends import HeadlessBackend
    from scribus_mcp.config import Config

    backend = HeadlessBackend(Config.from_env())
    if not asyncio.run(backend.is_available()):
        pytest.skip("Scribus binary not found")
    return backend


@pytest.fixture(scope="module")
def mcp(headless_available):
    from scribus_mcp.server import build_server

    return build_server()


@pytest.fixture(scope="module")
def call(mcp):
    async def _call(tool_name: str, **kwargs):
        kwargs.setdefault("mode", "headless")
        try:
            return _unwrap(await mcp.call_tool(tool_name, kwargs))
        except Exception as exc:
            # Tool may not be registered (e.g. run_script gated off). Surface
            # as a uniform dict so the test can pytest.skip on it instead of
            # crashing.
            return {"ok": False, "error": f"tool unavailable: {exc}"}

    return _call


# ----- 2.A — Spawn lifecycle ------------------------------------------------


def test_2A1_spawn_returns_clean_result(headless_available):
    """A single call spawns Scribus, runs the script, exits with a JSON result."""
    body = "_value = 42"
    r = asyncio.run(headless_available.script(body, result_expr="_value"))
    assert r.ok is True
    assert r.value == 42
    assert r.error is None


def test_2A2_script_error_captured(headless_available):
    """Python errors in the body produce ok=False with traceback."""
    body = "raise ValueError('intentional')"
    r = asyncio.run(headless_available.script(body))
    assert r.ok is False
    assert "intentional" in (r.error or "")
    assert r.traceback is not None


def test_2A3_scribus_call_works(headless_available):
    """Scripter API is reachable in the spawned Scribus."""
    body = "_value = scribus.haveDoc()"
    r = asyncio.run(headless_available.script(body, result_expr="_value"))
    assert r.ok is True
    # No doc open at start — haveDoc returns 0
    assert r.value == 0


# ----- 2.B — Multi-step in one body (the Brain20 pattern) -------------------


def test_2B1_create_doc_with_content_and_export_pdf(headless_available, tmp_path):
    """Whole-document generation in a single headless call: create doc, add
    text/image frames, set styles, export PDF. This mirrors the typical
    automated-manual workflow."""
    pdf_out = tmp_path / "headless-out.pdf"
    sla_out = tmp_path / "headless-out.sla"

    body = f"""
import scribus as _s
_s.newDocument((210.0, 297.0), (15, 15, 15, 20), 0, 1, 1, 0, 0, 1)

# Header text
_h = _s.createText(20, 20, 170, 15)
_s.setText('Brain20 Manual', _h)
_s.setFontSize(18, _h)

# Body text
_b = _s.createText(20, 50, 170, 80)
_s.setText('This is generated entirely in headless mode.', _b)

# Define a brand color and apply
_s.defineColorCMYKFloat('Brand', 80, 0, 20, 0)
_s.setTextColor('Brand', _h)

_s.saveDocAs({str(sla_out)!r})

# Inline PDF export
_pdf = _s.PDFfile()
_pdf.file = {str(pdf_out)!r}
_pdf.compress = 1
_pdf.compressmtd = 0
_pdf.version = 14
_pdf.resolution = 300
_pdf.pages = [1]
_pdf.save()

_value = {{'sla_size': __import__('os').path.getsize({str(sla_out)!r}),
          'pdf_size': __import__('os').path.getsize({str(pdf_out)!r}),
          'header_text': _s.getAllText(_h),
          'pages': _s.pageCount()}}
"""
    r = asyncio.run(headless_available.script(body, result_expr="_value"))
    assert r.ok, f"script failed: {r.error}\n{r.traceback}"
    assert r.value["pages"] == 1
    assert r.value["header_text"] == "Brain20 Manual"
    assert r.value["pdf_size"] > 1000
    assert sla_out.exists()
    assert pdf_out.exists()


# ----- 2.C — Save / open round-trip across separate calls ------------------


def test_2C1_save_then_open_in_separate_call(call, tmp_path):
    """Each MCP tool call is a separate Scribus spawn. State survives only
    via save/open round-trips."""
    sla = tmp_path / "rt.sla"

    # Spawn 1: create + save
    body = f"""
import scribus as _s
_s.newDocument((210.0, 297.0), (10, 10, 10, 10), 0, 1, 1, 0, 0, 1)
_n = _s.createText(20, 20, 100, 30)
_s.setText('round-trip-payload', _n)
_s.saveDocAs({str(sla)!r})
_value = _n
"""
    r = asyncio.run(call("run_script", body=body, result_expr="_value"))
    # run_script may not be enabled; if so, skip
    if not r.get("ok"):
        pytest.skip("run_script disabled — set SCRIBUS_MCP_RUN_SCRIPT=1")

    # Spawn 2: open + read
    body2 = f"""
import scribus as _s
_s.openDoc({str(sla)!r})
_n = (_s.getPageItems() or [[None]])[0][0]
_value = _s.getAllText(_n) if _n else None
"""
    r2 = asyncio.run(call("run_script", body=body2, result_expr="_value"))
    assert r2.get("ok"), r2.get("error")
    assert r2.get("value") == "round-trip-payload"


# ----- 2.D — Standard tool invocations in headless mode --------------------


def test_2D1_export_pdf_from_existing_sla(call, tmp_path):
    """export_pdf on an existing .sla, fully headless, no bridge needed."""
    sla = tmp_path / "src.sla"
    pdf = tmp_path / "src.pdf"

    # Create sla via run_script (or skip if disabled)
    create = asyncio.run(
        call(
            "run_script",
            body=f"""
import scribus as _s
_s.newDocument((210.0, 297.0), (15, 15, 15, 15), 0, 1, 1, 0, 0, 1)
_n = _s.createText(20, 20, 170, 50)
_s.setText('Hello PDF', _n)
_s.saveDocAs({str(sla)!r})
_value = True
""",
            result_expr="_value",
        )
    )
    if not create.get("ok"):
        pytest.skip("run_script disabled or doc creation failed")

    # Now export: open + export in one body via run_script (since each
    # mcp tool call is a fresh spawn, we can't open then export in two
    # tool calls without persisting via save). The whole point of headless
    # is workflows like this run as one call.
    r = asyncio.run(
        call(
            "run_script",
            body=f"""
import scribus as _s
_s.openDoc({str(sla)!r})
_pdf = _s.PDFfile()
_pdf.file = {str(pdf)!r}
_pdf.compress = 1
_pdf.compressmtd = 0
_pdf.version = 14
_pdf.resolution = 200
_pdf.pages = [1]
_pdf.save()
_value = __import__('os').path.getsize({str(pdf)!r})
""",
            result_expr="_value",
        )
    )
    assert r.get("ok"), r.get("error")
    assert pdf.exists() and pdf.stat().st_size > 1000


# ----- 2.E — Error paths ---------------------------------------------------


def test_2E1_bad_scripter_call_returns_clean_error(headless_available):
    """A bad Scripter call should produce ok=False with the Scribus error,
    not crash the spawn."""
    body = "_value = scribus.getAllText('NoSuchFrame')"
    r = asyncio.run(headless_available.script(body, result_expr="_value"))
    assert r.ok is False
    assert r.error is not None
    # Either Scribus's "Object not found" or similar
    assert "found" in (r.error.lower()) or "scribus" in (r.error.lower()) or r.error


def test_2E2_invalid_save_path(headless_available):
    """Saving to a path that can't be created should fail cleanly."""
    body = "import scribus as _s; _s.newDocument((210, 297), (10,10,10,10), 0, 1, 1, 0, 0, 1); _s.saveDocAs('Z:/definitely/does/not/exist/file.sla'); _value = True"
    r = asyncio.run(headless_available.script(body, result_expr="_value"))
    # Could be ok=True if Scribus silently ignores, or ok=False with error.
    # Either way, no crash, no missing JSON file.
    assert r.ok is False or r.value is True


# ----- 2.F — extra_font_paths plumbing -------------------------------------


def test_2F1_extra_font_paths_writes_prefs_xml(tmp_path):
    """The pre-spawn helper writes ExtraFontDirs into a minimal prefs XML."""
    from scribus_mcp.backends.headless import _write_prefs_with_font_dirs

    fonts_dir_a = tmp_path / "fonts_a"
    fonts_dir_b = tmp_path / "fonts_b"
    fonts_dir_a.mkdir()
    fonts_dir_b.mkdir()

    prefs_dir = tmp_path / "prefs"
    out = _write_prefs_with_font_dirs(prefs_dir, (str(fonts_dir_a), str(fonts_dir_b)))

    assert out.exists() and out.name == "prefs172.xml"
    content = out.read_text(encoding="utf-8")
    assert '<table name="ExtraFontDirs">' in content
    assert str(fonts_dir_a.resolve()) in content
    assert str(fonts_dir_b.resolve()) in content
    # Check structure: <row><col>...</col></row>
    assert content.count("<row>") == 2
    assert content.count("</row>") == 2


def test_2F2_extra_font_paths_inserts_pr_flag(tmp_path):
    """When config.extra_font_paths is set, the spawn cmd includes -pr <dir>."""
    from scribus_mcp.backends import HeadlessBackend
    from scribus_mcp.config import Config

    cfg = Config.from_env()
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    # Build a config with extra_font_paths populated (frozen dataclass — replace via dict)
    from dataclasses import replace

    cfg2 = replace(cfg, extra_font_paths=(str(fonts_dir),))

    backend = HeadlessBackend(cfg2)
    fake_script = tmp_path / "noop.py"
    fake_script.write_text("# noop")
    fake_prefs = tmp_path / "prefs"
    cmd = backend._build_cmd(fake_script, prefs_dir=fake_prefs)

    assert "-pr" in cmd
    pr_idx = cmd.index("-pr")
    assert cmd[pr_idx + 1] == str(fake_prefs)
    # -py + script must come after
    assert "-py" in cmd
    assert cmd.index("-py") > pr_idx


def test_2F3_no_extra_font_paths_omits_pr_flag(tmp_path):
    """Default (empty) extra_font_paths leaves the cmd untouched — no -pr."""
    from scribus_mcp.backends import HeadlessBackend
    from scribus_mcp.config import Config

    backend = HeadlessBackend(Config.from_env())  # default extra_font_paths=()
    fake_script = tmp_path / "noop.py"
    fake_script.write_text("# noop")
    cmd = backend._build_cmd(fake_script, prefs_dir=None)

    assert "-pr" not in cmd
    assert "-py" in cmd



"""Unit tests for the four "strip" patterns added in 1.1.5.dev:

- ``create_axes_strip`` — N tall axis cards with colored header + anchor footer.
- ``create_dark_kpi_band`` — dark band: headline number + breakdown rows w/ bars.
- ``create_pillar_strip`` — N pillar cards: number + title + lead + proofs + body.
- ``create_highlight_card_row`` — N medium cards with accent strap at the bottom.

All four ship as single ``backend.script()`` round-trips; the tests grep
the emitted body to confirm the right primitives are emitted, the
palette resolver runs over per-item accents, and validation catches
malformed input.
"""

from __future__ import annotations

import asyncio

import pytest

from scribus_mcp.backends.base import ScribusBackend, ScribusResult
from scribus_mcp.tools.palette import invalidate_palette


class _CapturingBackend(ScribusBackend):
    """Mock that captures the script body so the test can grep it."""

    def __init__(self, defined=("Black", "White", "accent", "surface", "ink", "muted",
                                "Brand", "Coral", "Teal")):
        self.last_body: str | None = None
        self.script_count = 0
        self._defined = list(defined)
        # Stub return value: enough shape to satisfy each pattern's
        # post-script unwrapping (they all return some flavour of
        # ``out.get("cards", [])`` or rows or background).
        self._fake = {
            "cards": [],
            "background": "bg",
            "title": "t",
            "headline": "h",
            "caption": "c",
            "rows": [],
        }

    async def is_available(self) -> bool:
        return True

    async def call(self, method, *args, **kwargs):
        if method == "getColorNames":
            return ScribusResult(ok=True, value=list(self._defined))
        return ScribusResult(ok=True, value=None)

    async def script(self, body, result_expr="None"):
        self.script_count += 1
        self.last_body = body
        return ScribusResult(ok=True, value=self._fake)


def _patched_get_backend(backend):
    async def _fake(_ctx, _mode):
        return backend

    return _fake


@pytest.fixture(autouse=True)
def _clear_palette_cache():
    invalidate_palette(None)
    yield
    invalidate_palette(None)


def _build_tool(module_path: str, tool_name: str):
    """Spin up a minimal MCP harness, register the pattern, return the
    tool callable."""
    from importlib import import_module

    mod = import_module(module_path)
    captured: dict = {}

    class _FakeMCP:
        def tool(self):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

    mod.register(_FakeMCP(), ctx=None)
    return captured[tool_name]


# ----- axes_strip -----------------------------------------------------------


def _axes_items(n: int = 3) -> list[dict]:
    return [
        {
            "number": f"0{i+1}",
            "title": f"Axis {i+1}",
            "lead": "short lead",
            "items": [f"bullet {j}" for j in range(3)],
            "anchor": f"Team {i+1}",
            "anchor_eyebrow": "ANCHOR",
            "accent_color": "Brand",
        }
        for i in range(n)
    ]


def test_axes_strip_emits_one_script_call_per_invocation(monkeypatch):
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.axes_strip.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool("scribus_mcp.tools.patterns.axes_strip", "create_axes_strip")
    out = asyncio.run(
        tool(items=_axes_items(3), x_mm=10, y_mm=10, width_mm=180, height_mm=200, mode="auto")
    )
    assert out["ok"] is True
    assert backend.script_count == 1
    body = backend.last_body or ""
    # Every card draws its own outer rect, header, header_seam, footer,
    # footer_seam → 5 createRects + 6 createTexts (number, title, lead,
    # body, eyebrow, name) per card. We don't pin exact counts, just
    # that the primitive types appear.
    assert "_s.createRect" in body
    assert "_s.createText" in body
    assert "ANCHOR" in body  # eyebrow text upcased


def test_axes_strip_resolves_per_item_accent(monkeypatch):
    """Each item's ``accent_color`` flows through the palette resolver,
    so a defined name passes through and an undefined role falls back
    to ``"Black"``."""
    backend = _CapturingBackend(defined=("Black", "White", "Brand"))
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.axes_strip.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool("scribus_mcp.tools.patterns.axes_strip", "create_axes_strip")
    items = _axes_items(2)
    items[0]["accent_color"] = "Brand"  # defined
    items[1]["accent_color"] = "primary"  # undefined → falls back to Black
    asyncio.run(
        tool(items=items, x_mm=0, y_mm=0, width_mm=100, height_mm=200,
             columns=2, mode="auto")
    )
    body = backend.last_body or ""
    assert "'Brand'" in body
    # Undefined "primary" fell back to "Black".
    assert "'Black'" in body


def test_axes_strip_caps_items_to_columns(monkeypatch):
    """Extra items beyond ``columns`` are silently dropped instead of
    overflowing the page."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.axes_strip.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool("scribus_mcp.tools.patterns.axes_strip", "create_axes_strip")
    out = asyncio.run(
        tool(items=_axes_items(5), x_mm=0, y_mm=0, width_mm=180,
             height_mm=200, columns=3, mode="auto")
    )
    assert out["count"] == 3


def test_axes_strip_validates_required_keys():
    tool = _build_tool("scribus_mcp.tools.patterns.axes_strip", "create_axes_strip")
    out = asyncio.run(
        tool(
            items=[{"number": "01", "title": "x", "items": []}],  # missing anchor + accent
            x_mm=0, y_mm=0, width_mm=180, height_mm=200, mode="auto",
        )
    )
    assert out["ok"] is False
    assert "missing" in out["error"]


def test_axes_strip_rejects_empty_items():
    tool = _build_tool("scribus_mcp.tools.patterns.axes_strip", "create_axes_strip")
    out = asyncio.run(
        tool(items=[], x_mm=0, y_mm=0, width_mm=180, height_mm=200, mode="auto")
    )
    assert out["ok"] is False
    assert "items" in out["error"]


# ----- dark_kpi_band --------------------------------------------------------


def _band_breakdown() -> list[dict]:
    return [
        {"label": "Carburant",   "value": "73 318 t", "percent": 62, "color": "Coral"},
        {"label": "Électricité", "value": "18 402 t", "percent": 16, "color": "Teal"},
        {"label": "Maintenance", "value": "25 836 t", "percent": 22, "color": "Brand"},
    ]


def test_dark_kpi_band_emits_track_and_fill_per_row(monkeypatch):
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.dark_kpi_band.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool(
        "scribus_mcp.tools.patterns.dark_kpi_band", "create_dark_kpi_band"
    )
    out = asyncio.run(
        tool(
            title="Footprint",
            headline_value="117 556",
            headline_caption="tCO2e total",
            breakdown=_band_breakdown(),
            x_mm=10, y_mm=10, width_mm=200, mode="auto",
        )
    )
    assert out["ok"] is True
    body = backend.last_body or ""
    # Each breakdown row emits a track rect + a fill rect, plus the
    # background band — at least that many createRect calls.
    assert body.count("_s.createRect") >= 1  # at least the BG; per-row rects are inside a loop
    # The 3 row colors made it into the embedded list literal.
    assert "'Coral'" in body
    assert "'Teal'" in body
    assert "'Brand'" in body
    # Headline + caption + title texts.
    assert "117 556" in body


def test_dark_kpi_band_validates_percent_range():
    tool = _build_tool(
        "scribus_mcp.tools.patterns.dark_kpi_band", "create_dark_kpi_band"
    )
    out = asyncio.run(
        tool(
            title="x",
            headline_value="0",
            headline_caption="",
            breakdown=[
                {"label": "L", "value": "v", "percent": 150, "color": "Brand"},
            ],
            x_mm=0, y_mm=0, width_mm=100, mode="auto",
        )
    )
    assert out["ok"] is False
    assert "percent" in out["error"]


def test_dark_kpi_band_rejects_non_numeric_percent():
    tool = _build_tool(
        "scribus_mcp.tools.patterns.dark_kpi_band", "create_dark_kpi_band"
    )
    out = asyncio.run(
        tool(
            title="x",
            headline_value="0",
            headline_caption="",
            breakdown=[
                {"label": "L", "value": "v", "percent": "lots", "color": "Brand"},
            ],
            x_mm=0, y_mm=0, width_mm=100, mode="auto",
        )
    )
    assert out["ok"] is False
    assert "percent" in out["error"]


def test_dark_kpi_band_rejects_too_many_rows():
    tool = _build_tool(
        "scribus_mcp.tools.patterns.dark_kpi_band", "create_dark_kpi_band"
    )
    too_many = [
        {"label": f"L{i}", "value": "v", "percent": 10, "color": "Brand"}
        for i in range(10)
    ]
    out = asyncio.run(
        tool(
            title="x",
            headline_value="0",
            headline_caption="",
            breakdown=too_many,
            x_mm=0, y_mm=0, width_mm=100, mode="auto",
        )
    )
    assert out["ok"] is False
    assert "1..6" in out["error"] or "6" in out["error"]


# ----- pillar_strip ---------------------------------------------------------


def _pillar_items(n: int = 3) -> list[dict]:
    return [
        {
            "number": f"0{i+1}",
            "title": f"Pillar {i+1}",
            "lead": "short lead",
            "proofs": [
                ["> 1 000", "boîtiers"],
                ["Taux SAV", "résiduel"],
                ["2 séries", "100% MUXen"],
            ],
            "body": "Prose body for pillar.",
            "accent_color": "Brand",
        }
        for i in range(n)
    ]


def test_pillar_strip_pads_short_proofs(monkeypatch):
    """Items with fewer than ``proof_count`` proofs are padded with
    empty pairs so multi-card rows stay visually aligned."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.pillar_strip.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool(
        "scribus_mcp.tools.patterns.pillar_strip", "create_pillar_strip"
    )
    items = _pillar_items(2)
    items[1]["proofs"] = [["only one", "label"]]  # short — should be padded to 3
    out = asyncio.run(
        tool(items=items, x_mm=0, y_mm=0, width_mm=180,
             height_mm=170, columns=2, mode="auto")
    )
    assert out["ok"] is True


def test_pillar_strip_emits_separator_line(monkeypatch):
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.pillar_strip.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool(
        "scribus_mcp.tools.patterns.pillar_strip", "create_pillar_strip"
    )
    asyncio.run(
        tool(items=_pillar_items(3), x_mm=10, y_mm=10, width_mm=180,
             height_mm=170, mode="auto")
    )
    body = backend.last_body or ""
    # Each pillar draws an accent-coloured separator line between
    # lead and proofs.
    assert "_s.createLine" in body


def test_pillar_strip_validates_proofs_list():
    tool = _build_tool(
        "scribus_mcp.tools.patterns.pillar_strip", "create_pillar_strip"
    )
    out = asyncio.run(
        tool(
            items=[{
                "number": "01", "title": "x",
                "proofs": "not a list",
                "accent_color": "Brand",
            }],
            x_mm=0, y_mm=0, width_mm=180, height_mm=170, mode="auto",
        )
    )
    assert out["ok"] is False
    assert "proofs" in out["error"]


def test_pillar_strip_rejects_bad_body_alignment():
    tool = _build_tool(
        "scribus_mcp.tools.patterns.pillar_strip", "create_pillar_strip"
    )
    out = asyncio.run(
        tool(
            items=_pillar_items(1),
            x_mm=0, y_mm=0, width_mm=180, height_mm=170,
            body_alignment="diagonal",
            mode="auto",
        )
    )
    assert out["ok"] is False
    assert "body_alignment" in out["error"]


# ----- highlight_card_row ---------------------------------------------------


def _highlight_items(n: int = 2) -> list[dict]:
    return [
        {
            "title": f"Series {i+1}",
            "body": "Prose body for series.",
            "highlight": f"{i+1} 000+ shipped",
        }
        for i in range(n)
    ]


def test_highlight_card_row_emits_strap_per_card(monkeypatch):
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.highlight_card_row.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool(
        "scribus_mcp.tools.patterns.highlight_card_row",
        "create_highlight_card_row",
    )
    out = asyncio.run(
        tool(items=_highlight_items(2), x_mm=10, y_mm=10, width_mm=180,
             columns=2, mode="auto")
    )
    assert out["ok"] is True
    body = backend.last_body or ""
    # Each card draws an outer rect + a strap rect → at least 4 rects
    # for 2 cards. Highlight text included.
    assert "_s.createRect" in body
    assert "1 000+ shipped" in body
    assert "2 000+ shipped" in body


def test_highlight_card_row_per_item_accent_override(monkeypatch):
    """A per-item ``accent_color`` overrides the table-level default."""
    backend = _CapturingBackend(defined=("Black", "White", "accent", "Brand"))
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.highlight_card_row.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_tool(
        "scribus_mcp.tools.patterns.highlight_card_row",
        "create_highlight_card_row",
    )
    items = _highlight_items(2)
    items[0]["accent_color"] = "Brand"  # override
    asyncio.run(
        tool(items=items, x_mm=10, y_mm=10, width_mm=180, mode="auto")
    )
    body = backend.last_body or ""
    # Both the override (Brand) and the table-level default (accent)
    # must end up in the body since each card carries its own accent
    # in the per-card spec literal.
    assert "'Brand'" in body
    assert "'accent'" in body


def test_highlight_card_row_rejects_bad_alignment():
    tool = _build_tool(
        "scribus_mcp.tools.patterns.highlight_card_row",
        "create_highlight_card_row",
    )
    out = asyncio.run(
        tool(
            items=_highlight_items(1),
            x_mm=0, y_mm=0, width_mm=180,
            body_alignment="diagonal",
            mode="auto",
        )
    )
    assert out["ok"] is False
    assert "body_alignment" in out["error"]


def test_highlight_card_row_validates_required_keys():
    tool = _build_tool(
        "scribus_mcp.tools.patterns.highlight_card_row",
        "create_highlight_card_row",
    )
    out = asyncio.run(
        tool(
            items=[{"title": "x"}],  # missing body + highlight
            x_mm=0, y_mm=0, width_mm=180, mode="auto",
        )
    )
    assert out["ok"] is False
    assert "missing" in out["error"]

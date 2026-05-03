"""Unit tests asserting that patterns emit a single ``backend.script()``
call instead of N ``backend.call()`` calls. This is the structural win
that makes patterns usable in headless mode (where each ``backend.call``
spawns a fresh Scribus process at ~3 s each).

These tests run against a counting mock backend — no Scribus needed.
"""

from __future__ import annotations

import asyncio

import pytest

from scribus_mcp.backends.base import ScribusBackend, ScribusResult


class _CountingBackend(ScribusBackend):
    """Mock that counts calls + scripts, returns a fake-but-plausible
    Scribus result for each. Used to assert the pattern's emit shape."""

    def __init__(self, fake_value=None):
        self.call_count = 0
        self.script_count = 0
        self.last_script_body: str | None = None
        self.last_result_expr: str | None = None
        self._fake_value = fake_value

    async def is_available(self) -> bool:
        return True

    async def call(self, method, *args, **kwargs):
        self.call_count += 1
        # Return a stub name for createX / generic ok for setX
        if method.startswith("create"):
            return ScribusResult(ok=True, value=f"obj_{self.call_count}")
        return ScribusResult(ok=True, value=None)

    async def script(self, body, result_expr="None"):
        self.script_count += 1
        self.last_script_body = body
        self.last_result_expr = result_expr
        # Return whatever fake_value was configured — typically the dict
        # of name lists the pattern's body builds.
        return ScribusResult(ok=True, value=self._fake_value)


def _patched_get_backend(backend):
    """Build a coroutine that replaces ``get_backend`` so the pattern
    sees our counting mock instead of resolving to interactive/headless."""

    async def _fake(_ctx, _mode):
        return backend

    return _fake


@pytest.fixture
def patched_backend(monkeypatch):
    """Monkey-patch every pattern module's ``get_backend`` to return a
    shared counting backend. Yields the backend so tests can inspect
    counts after running the tool."""
    fake_value = {
        "bars": ["b1", "b2", "b3", "b4"],
        "gridlines": ["g1", "g2", "g3", "g4"],
        "labels": ["l1", "l2", "l3", "l4"],
        "value_labels": [],
        "legend": [],
    }
    backend = _CountingBackend(fake_value=fake_value)
    fake = _patched_get_backend(backend)
    # Patch in every module that imports get_backend at module load time.
    import scribus_mcp.tools.patterns.bar_chart as bar_chart_mod

    monkeypatch.setattr(bar_chart_mod, "get_backend", fake)
    yield backend


def _build_bar_chart_tool():
    """Spin up a minimal MCP harness, register bar_chart, return the
    callable for the tool function."""
    from scribus_mcp.tools.patterns import bar_chart as bar_chart_mod

    captured: dict = {}

    class _FakeMCP:
        def tool(self):
            def deco(fn):
                captured["fn"] = fn
                return fn

            return deco

    bar_chart_mod.register(_FakeMCP(), ctx=None)
    return captured["fn"]


def test_bar_chart_emits_one_script_call_single_dataset(patched_backend):
    """create_bar_chart should make exactly one backend.script() call
    (and zero backend.call() calls) for a single-dataset chart."""
    bar_chart = _build_bar_chart_tool()
    r = asyncio.run(
        bar_chart(
            labels=["Q1", "Q2", "Q3", "Q4"],
            values=[1, 2, 3, 4],
            x_mm=10, y_mm=10, width_mm=100, height_mm=50,
            mode="auto",
        )
    )
    assert r["ok"] is True
    assert patched_backend.script_count == 1
    assert patched_backend.call_count == 0
    # The body must reference every primitive type the chart needs.
    body = patched_backend.last_script_body or ""
    assert "_s.createLine" in body  # gridlines
    assert "_s.createRect" in body  # bars
    assert "_s.createText" in body  # category labels


def test_bar_chart_emits_one_script_call_multi_dataset(patched_backend):
    """Multi-dataset chart with show_values + legend should still be
    exactly one script call."""
    bar_chart = _build_bar_chart_tool()
    r = asyncio.run(
        bar_chart(
            labels=["A", "B", "C"],
            datasets=[
                {"label": "X", "values": [1, 2, 3], "fill_color": "Black"},
                {"label": "Y", "values": [4, 5, 6], "fill_color": "Black"},
            ],
            x_mm=10, y_mm=10, width_mm=100, height_mm=60,
            show_values=True,
            mode="auto",
        )
    )
    assert r["ok"] is True
    assert patched_backend.script_count == 1
    assert patched_backend.call_count == 0


def test_bar_chart_validation_short_circuits_before_backend(patched_backend):
    """Validation errors should not spawn Scribus at all."""
    bar_chart = _build_bar_chart_tool()
    r = asyncio.run(
        bar_chart(
            labels=["A", "B"],
            values=[1],  # length mismatch
            x_mm=0, y_mm=0, width_mm=50, height_mm=20,
            mode="auto",
        )
    )
    assert r["ok"] is False
    assert "same length" in r["error"]
    assert patched_backend.script_count == 0
    assert patched_backend.call_count == 0


def test_bar_chart_bbox_is_inclusive(patched_backend):
    """Returned bbox.height_mm must equal the input height_mm — the
    'inclusive' invariant the docstring promises."""
    bar_chart = _build_bar_chart_tool()
    r = asyncio.run(
        bar_chart(
            labels=["A", "B"],
            values=[1, 2],
            x_mm=10, y_mm=20, width_mm=100, height_mm=40,
            show_values=True,
            mode="auto",
        )
    )
    assert r["ok"] is True
    assert r["bbox"]["x_mm"] == 10
    assert r["bbox"]["y_mm"] == 20
    assert r["bbox"]["width_mm"] == 100
    assert r["bbox"]["height_mm"] == 40


def test_bar_chart_bbox_inclusive_multi_dataset_with_show_values(patched_backend):
    """The strip math (bottom labels + legend + value labels) is most
    fragile in the multi-dataset+show_values combo. The bbox must still
    match the input height_mm exactly."""
    bar_chart = _build_bar_chart_tool()
    r = asyncio.run(
        bar_chart(
            labels=["Q1", "Q2", "Q3", "Q4"],
            datasets=[
                {"label": "X", "values": [1, 2, 3, 4], "fill_color": "Black"},
                {"label": "Y", "values": [5, 6, 7, 8], "fill_color": "Black"},
                {"label": "Z", "values": [3, 5, 7, 9], "fill_color": "Black"},
            ],
            x_mm=15, y_mm=25, width_mm=170, height_mm=70,
            show_values=True,
            mode="auto",
        )
    )
    assert r["ok"] is True
    bbox = r["bbox"]
    assert bbox["x_mm"] == 15
    assert bbox["y_mm"] == 25
    assert bbox["width_mm"] == 170
    assert bbox["height_mm"] == 70  # inclusive of all 3 strips


def test_bar_chart_height_too_small_for_strips(patched_backend):
    """If height_mm is smaller than the reserved strips, surface a
    descriptive error rather than producing a degenerate chart."""
    bar_chart = _build_bar_chart_tool()
    r = asyncio.run(
        bar_chart(
            labels=["A"],
            datasets=[
                {"label": "X", "values": [1], "fill_color": "Black"},
                {"label": "Y", "values": [2], "fill_color": "Black"},
            ],
            x_mm=0, y_mm=0, width_mm=50, height_mm=10,
            show_values=True,  # adds a 6 mm top strip
            mode="auto",
        )
    )
    # 6 (top) + 6 (legend) + 6 (bottom labels) = 18 mm > 10 mm height
    assert r["ok"] is False
    assert "too small" in r["error"]

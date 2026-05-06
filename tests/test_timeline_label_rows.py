"""``create_timeline(label_rows=N)`` — labels stagger across N y-rows.

Regression for the "A DECADE OF RELEASES" timeline where six items
packed into one width-mm produced labels so narrow they truncated and
ran into each other ("v1.0 — first rLeolenags-teerm support"). With
``label_rows=2``, adjacent items alternate between two y-rows so each
label competes only with the same-row neighbour two markers away,
roughly doubling its horizontal slot.
"""

from __future__ import annotations

import asyncio
import re

import pytest

from scribus_mcp.backends.base import ScribusBackend, ScribusResult


class _CapturingBackend(ScribusBackend):
    """Mock that captures the script body so the test can grep it."""

    def __init__(self):
        self.last_body: str | None = None

    async def is_available(self) -> bool:
        return True

    async def call(self, method, *args, **kwargs):
        if method == "getColorNames":
            return ScribusResult(ok=True, value=["Black"])
        return ScribusResult(ok=True, value=None)

    async def script(self, body, result_expr="None"):
        self.last_body = body
        return ScribusResult(
            ok=True,
            value={"axis": "a", "markers": [], "connectors": [], "labels": [], "dates": []},
        )


def _build_timeline_tool():
    """Spin up a minimal MCP harness and return the create_timeline callable."""
    from scribus_mcp.tools.patterns import timeline as timeline_mod

    captured: dict = {}

    class _FakeMCP:
        def tool(self):
            def deco(fn):
                captured["fn"] = fn
                return fn

            return deco

    timeline_mod.register(_FakeMCP(), ctx=None)
    return captured["fn"]


def _patched_get_backend(backend):
    async def _fake(_ctx, _mode):
        return backend

    return _fake


@pytest.fixture(autouse=True)
def _clear_palette_cache():
    from scribus_mcp.tools.palette import invalidate_palette

    invalidate_palette(None)
    yield
    invalidate_palette(None)


def _labels_section(body: str) -> str:
    """Slice the section of the script body between ``_label_names = []``
    and ``_date_names = []`` so regex parsing doesn't confuse label
    tuples with date tuples (both share the same ``(x,y,w,h,text)``
    shape)."""
    start = body.find("_label_names = []")
    end = body.find("_date_names = []")
    if start < 0 or end < 0 or end < start:
        return body
    return body[start:end]


def _label_y_values(body: str) -> list[float]:
    """Extract per-label y values from the labels block."""
    section = _labels_section(body)
    return [
        float(m.group(2))
        for m in re.finditer(
            r"\((-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?), \d+(?:\.\d+)?, 5\.0, '([^']+)'\)",
            section,
        )
    ]


def test_label_rows_default_keeps_single_row(monkeypatch):
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.timeline.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_timeline_tool()
    asyncio.run(
        tool(
            items=[
                {"position": 0.0, "label": "A", "date": "2016"},
                {"position": 0.5, "label": "B", "date": "2020"},
                {"position": 1.0, "label": "C", "date": "2024"},
            ],
            x_mm=10, width_mm=180,
            top_y_mm=10,
            mode="auto",
        )
    )
    ys = _label_y_values(backend.last_body or "")
    assert ys, "no labels emitted in script body"
    # All labels share the same y when label_rows=1 (default).
    assert len(set(ys)) == 1, f"expected a single y, got {sorted(set(ys))}"


def test_label_rows_two_alternates_y(monkeypatch):
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.timeline.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_timeline_tool()
    asyncio.run(
        tool(
            items=[
                {"position": 0.0, "label": "A"},
                {"position": 0.2, "label": "B"},
                {"position": 0.4, "label": "C"},
                {"position": 0.6, "label": "D"},
                {"position": 0.8, "label": "E"},
                {"position": 1.0, "label": "F"},
            ],
            x_mm=10, width_mm=180,
            top_y_mm=10,
            label_rows=2,
            mode="auto",
        )
    )
    ys = _label_y_values(backend.last_body or "")
    assert len(ys) == 6
    # Two distinct y values, alternating: items 0, 2, 4 share row 0
    # (above the axis); items 1, 3, 5 share row 1 (below the axis). In
    # Scribus screen coords y grows downward, so the above row has the
    # smaller numerical y.
    distinct = sorted(set(ys))
    assert len(distinct) == 2, f"expected 2 rows, got {distinct}"
    row0_y, row1_y = distinct[0], distinct[1]  # row0 above (smaller y), row1 below
    assert ys[0] == ys[2] == ys[4] == row0_y
    assert ys[1] == ys[3] == ys[5] == row1_y


def test_label_rows_two_doubles_horizontal_slot(monkeypatch):
    """With label_rows=2, each label's bounded width should reflect the
    distance to the same-row neighbour (2 marker steps away), not the
    immediate neighbour."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.timeline.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_timeline_tool()
    asyncio.run(
        tool(
            items=[
                {"position": 0.0, "label": "A"},
                {"position": 0.2, "label": "B"},
                {"position": 0.4, "label": "C"},
                {"position": 0.6, "label": "D"},
                {"position": 0.8, "label": "E"},
                {"position": 1.0, "label": "F"},
            ],
            x_mm=0, width_mm=100,
            top_y_mm=10,
            label_rows=2,
            mode="auto",
        )
    )
    section = _labels_section(backend.last_body or "")
    # Each marker step = 0.2 * 100 = 20 mm. With label_rows=2 the
    # same-row neighbour is 2 steps = 40 mm away. Width is bounded by
    # 0.95 * neighbour distance, capped at 40 mm. So labels should be
    # ~38 mm wide (2-step) vs ~19 mm wide (1-step) — much more room.
    widths = [
        float(m.group(1))
        for m in re.finditer(
            r"\(-?\d+(?:\.\d+)?, -?\d+(?:\.\d+)?, (\d+(?:\.\d+)?), 5\.0, '[A-F]'\)",
            section,
        )
    ]
    assert widths, "no labels parsed"
    # Inner labels (B, C, D, E) should have ~38 mm width.
    inner_widths = widths[1:-1]
    assert all(w > 30 for w in inner_widths), (
        f"label_rows=2 should give 30+ mm slots; got {inner_widths}"
    )


def test_label_rows_two_extends_below_axis(monkeypatch):
    """Two-row mode splits items above/below the axis. With dates the
    label has to step further out to clear the date row, so the bbox is
    materially taller than the single-row equivalent and dips well below
    the axis line."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.timeline.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_timeline_tool()
    items = [{"position": i / 5, "label": f"L{i}", "date": f"{2020 + i}"} for i in range(6)]
    one_row = asyncio.run(
        tool(items=items, x_mm=10, width_mm=180, top_y_mm=20, mode="auto")
    )
    two_rows = asyncio.run(
        tool(
            items=items, x_mm=10, width_mm=180, top_y_mm=20,
            label_rows=2, mode="auto",
        )
    )
    # Two-row mode is meaningfully taller — at least one full label
    # height (bumped side_anchor + below-side label stack).
    assert two_rows["bbox"]["height_mm"] > one_row["bbox"]["height_mm"]
    assert two_rows["bbox"]["height_mm"] - one_row["bbox"]["height_mm"] >= 5.0
    # Top still anchored at top_y_mm.
    assert abs(two_rows["bbox"]["y_mm"] - 20) < 0.5


def test_label_rows_auto_short_labels_stay_single_row(monkeypatch):
    """Short labels fit comfortably in their single-row slot — auto
    keeps the timeline at 1 row."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.timeline.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_timeline_tool()
    out = asyncio.run(
        tool(
            items=[
                {"position": 0.0, "label": "A"},
                {"position": 0.5, "label": "B"},
                {"position": 1.0, "label": "C"},
            ],
            x_mm=10, width_mm=180, top_y_mm=10,
            label_rows="auto",
            mode="auto",
        )
    )
    assert out["ok"] is True
    assert out["label_rows"] == 1


def test_label_rows_auto_long_labels_bump_to_two(monkeypatch):
    """Long labels packed into a narrow timeline overflow single-row
    slots — auto bumps to 2 rows so each label competes with the
    same-row neighbour 2 markers away."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.timeline.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_timeline_tool()
    out = asyncio.run(
        tool(
            items=[
                {"position": 0.0, "label": "v1.0 — first release"},
                {"position": 0.2, "label": "long-term support"},
                {"position": 0.4, "label": "Bluetooth Mesh"},
                {"position": 0.6, "label": "v3.0, west modules"},
                {"position": 0.8, "label": "LTS v3.7, Matter"},
                {"position": 1.0, "label": "Rust support, v4.x"},
            ],
            x_mm=10, width_mm=180, top_y_mm=10,
            label_rows="auto",
            mode="auto",
        )
    )
    assert out["ok"] is True
    assert out["label_rows"] == 2


def test_label_rows_auto_explicit_int_overrides(monkeypatch):
    """Passing an int forces the timeline to use that row count even
    when auto would have picked something else."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.timeline.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_timeline_tool()
    out = asyncio.run(
        tool(
            items=[
                {"position": 0.0, "label": "v1.0 — first release"},
                {"position": 0.2, "label": "long-term support"},
                {"position": 0.4, "label": "Bluetooth Mesh"},
            ],
            x_mm=10, width_mm=180, top_y_mm=10,
            label_rows=1,  # force single row
            mode="auto",
        )
    )
    assert out["ok"] is True
    assert out["label_rows"] == 1  # respected even though auto would say 2


def test_label_rows_validation_rejects_unknown_string():
    backend = _CapturingBackend()
    import scribus_mcp.tools.patterns.timeline as tm

    tm.get_backend = _patched_get_backend(backend)  # type: ignore[attr-defined]
    tool = _build_timeline_tool()
    out = asyncio.run(
        tool(
            items=[{"position": 0.5, "label": "A"}],
            x_mm=10, width_mm=180, top_y_mm=10,
            label_rows="banana", mode="auto",
        )
    )
    assert out["ok"] is False
    assert "label_rows" in out["error"]


def test_label_rows_validation_rejects_zero():
    backend = _CapturingBackend()
    import scribus_mcp.tools.patterns.timeline as tm

    tm.get_backend = _patched_get_backend(backend)  # type: ignore[attr-defined]
    tool = _build_timeline_tool()
    out = asyncio.run(
        tool(
            items=[{"position": 0.5, "label": "A"}],
            x_mm=10, width_mm=180, top_y_mm=10,
            label_rows=0, mode="auto",
        )
    )
    assert out["ok"] is False
    assert "label_rows" in out["error"]

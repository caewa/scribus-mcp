"""``create_comparison_table(rows=[{cells, highlight}])`` — per-row
accent stripe at the left edge for "this is the recommended option"
emphasis without the noise of zebra-shading the whole row.

Covers the two row shapes (legacy ``list[str]`` vs. new ``dict``),
the per-row colour override, and the cell-text shift that prevents
the highlight stripe from overlapping the first cell's text.
"""

from __future__ import annotations

import asyncio
import re

import pytest

from scribus_mcp.backends.base import ScribusBackend, ScribusResult


class _CapturingBackend(ScribusBackend):
    def __init__(self, defined=("Black", "accent", "Brand")):
        self.last_body: str | None = None
        self._defined = list(defined)

    async def is_available(self) -> bool:
        return True

    async def call(self, method, *args, **kwargs):
        if method == "getColorNames":
            return ScribusResult(ok=True, value=list(self._defined))
        return ScribusResult(ok=True, value=None)

    async def script(self, body, result_expr="None"):
        if "_s.groupObjects" in body:
            return ScribusResult(ok=True, value=None)
        self.last_body = body
        return ScribusResult(
            ok=True,
            value={
                "headers": [],
                "rule": "r",
                "zebra": [],
                "highlights": ["h0"],
                "cells": [["c0", "c1", "c2"]],
            },
        )


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


def _build_table_tool():
    from scribus_mcp.tools.patterns import comparison_table as mod

    captured: dict = {}

    class _FakeMCP:
        def tool(self):
            def deco(fn):
                captured["fn"] = fn
                return fn

            return deco

    mod.register(_FakeMCP(), ctx=None)
    return captured["fn"]


def _highlight_section(body: str) -> str:
    """Slice out the highlight loop from the script body."""
    start = body.find("_highlight_names = []")
    end = body.find("_cell_rows")
    if start < 0 or end < 0:
        return body
    return body[start:end]


def test_legacy_list_rows_emit_no_highlights(monkeypatch):
    """Plain ``list[str]`` rows produce zero highlight rects — the new
    feature is opt-in, no behaviour change for existing scripts."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.comparison_table.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_table_tool()
    out = asyncio.run(
        tool(
            headers=["A", "B", "C"],
            rows=[["1", "2", "3"], ["4", "5", "6"]],
            x_mm=10, y_mm=10, width_mm=100,
            mode="auto",
        )
    )
    assert out["ok"] is True
    section = _highlight_section(backend.last_body or "")
    # The highlight_spec literal embedded in the body should be empty.
    assert "in []" in section, "expected empty highlight_spec for plain rows"


def test_dict_row_with_highlight_emits_rect(monkeypatch):
    """A dict row with ``highlight=True`` produces one highlight rect
    using the table-level ``highlight_color`` (default palette role)."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.comparison_table.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_table_tool()
    asyncio.run(
        tool(
            headers=["A", "B", "C"],
            rows=[
                ["1", "2", "3"],
                {"cells": ["4", "5", "6"], "highlight": True},
                ["7", "8", "9"],
            ],
            x_mm=10, y_mm=10, width_mm=100,
            mode="auto",
        )
    )
    section = _highlight_section(backend.last_body or "")
    # One tuple in the highlight_spec literal — for the 2nd row.
    assert section.count("(10, ") == 1 or re.search(
        r"\[\(10(?:\.0)?, ", section
    ), f"expected one highlight rect; section was:\n{section}"
    # Default highlight_color is the palette role 'accent', which we
    # defined in the mock — so the script should reference 'accent'.
    assert "'accent'" in section


def test_dict_row_per_item_color_override(monkeypatch):
    """Per-row ``highlight_color`` overrides the table-level default."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.comparison_table.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_table_tool()
    asyncio.run(
        tool(
            headers=["A", "B", "C"],
            rows=[
                {"cells": ["1", "2", "3"], "highlight": True, "highlight_color": "Brand"},
            ],
            x_mm=10, y_mm=10, width_mm=100,
            mode="auto",
        )
    )
    section = _highlight_section(backend.last_body or "")
    assert "'Brand'" in section


def test_highlight_shifts_first_cell_text(monkeypatch):
    """The first cell of a highlighted row must be shifted right + made
    narrower so the stripe doesn't overlap the text."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.comparison_table.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_table_tool()
    asyncio.run(
        tool(
            headers=["A", "B", "C"],
            rows=[{"cells": ["one", "two", "three"], "highlight": True}],
            x_mm=10, y_mm=20, width_mm=90,  # 30 mm per col
            highlight_width_mm=2.0,
            mode="auto",
        )
    )
    body = backend.last_body or ""
    # Cells are emitted as (r_idx, x, y, w, h, 'text'). The "one" cell
    # is the first column of row 0 — match that 6-tuple specifically.
    m = re.search(
        r"\(\d+,\s*(\d+(?:\.\d+)?),\s*\d+(?:\.\d+)?,\s*(\d+(?:\.\d+)?),"
        r"[^)]*'one'\)",
        body,
    )
    assert m is not None, f"didn't find 'one' cell tuple in body:\n{body}"
    cell_x = float(m.group(1))
    cell_w = float(m.group(2))
    assert cell_x > 10, f"first cell of highlighted row not shifted; x={cell_x}"
    assert cell_w < 30, f"first cell of highlighted row not narrowed; w={cell_w}"


def test_dict_row_missing_cells_errors(monkeypatch):
    """A dict row that doesn't carry ``cells`` returns a clear error."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.comparison_table.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_table_tool()
    out = asyncio.run(
        tool(
            headers=["A", "B"],
            rows=[{"highlight": True}],
            x_mm=10, y_mm=10, width_mm=100,
            mode="auto",
        )
    )
    assert out["ok"] is False
    assert "cells" in out["error"]


def test_mixed_row_shapes_normalised(monkeypatch):
    """Plain-list and dict rows can be mixed in the same call."""
    backend = _CapturingBackend()
    monkeypatch.setattr(
        "scribus_mcp.tools.patterns.comparison_table.get_backend",
        _patched_get_backend(backend),
    )
    tool = _build_table_tool()
    out = asyncio.run(
        tool(
            headers=["A", "B"],
            rows=[
                ["x", "y"],                           # legacy list
                {"cells": ["p", "q"], "highlight": True},  # dict, highlighted
                ["m", "n"],                           # legacy list
            ],
            x_mm=10, y_mm=10, width_mm=100,
            mode="auto",
        )
    )
    assert out["ok"] is True
    assert out["rows_drawn"] == 3

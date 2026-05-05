"""Shape primitives now accept fill_color / line_color / shade / width
inline. Verify the script body the tool sends to Scribus actually emits
the styling calls — earlier versions silently dropped these args.

Regression: an LLM passing ``fill_color="Brand"`` to ``create_rectangle``
got ``ok: true`` back but the rendered shape had no fill, because the
tool's signature didn't declare ``fill_color`` and the framework
filtered it out.
"""

from __future__ import annotations

import asyncio

import pytest

from scribus_mcp.backends.base import ScribusBackend, ScribusResult
from scribus_mcp.tools.palette import invalidate_palette


class _CapturingBackend(ScribusBackend):
    """Mock backend that captures the last script body so tests can
    assert on the emitted Scribus calls."""

    def __init__(self, defined_colors=("Black", "Brand")):
        self._colors = list(defined_colors)
        self.last_script_body: str | None = None
        self.script_count = 0
        self.call_count = 0

    async def is_available(self) -> bool:
        return True

    async def call(self, method, *args, **kwargs):
        self.call_count += 1
        if method == "getColorNames":
            return ScribusResult(ok=True, value=list(self._colors))
        return ScribusResult(ok=True, value=None)

    async def script(self, body, result_expr="None"):
        self.script_count += 1
        self.last_script_body = body
        return ScribusResult(ok=True, value="r1")


def _patched_get_backend(backend):
    async def _fake(_ctx, _mode):
        return backend

    return _fake


@pytest.fixture(autouse=True)
def _clear_palette_cache():
    invalidate_palette(None)
    yield
    invalidate_palette(None)


@pytest.fixture
def patched_shapes(monkeypatch):
    backend = _CapturingBackend()
    fake = _patched_get_backend(backend)
    import scribus_mcp.tools.shapes as shapes_mod

    monkeypatch.setattr(shapes_mod, "get_backend", fake)
    return backend


def _build_tool(name: str):
    """Spin up a minimal MCP harness, register shapes, return the
    callable for the named tool."""
    from scribus_mcp.tools import shapes as shapes_mod

    captured: dict = {}

    class _FakeMCP:
        def tool(self):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

    shapes_mod.register(_FakeMCP(), ctx=None)
    return captured[name]


def test_create_rectangle_emits_setFillColor_when_passed(patched_shapes):
    create_rectangle = _build_tool("create_rectangle")
    asyncio.run(
        create_rectangle(
            x_mm=10, y_mm=10, width_mm=50, height_mm=50,
            fill_color="Brand",
            mode="auto",
        )
    )
    body = patched_shapes.last_script_body
    assert body is not None
    assert "_s.createRect(10, 10, 50, 50)" in body
    # The styling line is the regression: must apply the requested fill.
    assert "_s.setFillColor('Brand', _v)" in body


def test_create_rectangle_line_color_none_suppresses_stroke(patched_shapes):
    create_rectangle = _build_tool("create_rectangle")
    asyncio.run(
        create_rectangle(
            x_mm=0, y_mm=0, width_mm=10, height_mm=10,
            line_color="None",
            mode="auto",
        )
    )
    body = patched_shapes.last_script_body
    # "None" → setLineColor("None") + width 0, not the default 1pt black.
    assert '_s.setLineColor("None", _v)' in body
    assert "_s.setLineWidth(0, _v)" in body


def test_create_rectangle_no_styling_args_keeps_creation_only(patched_shapes):
    create_rectangle = _build_tool("create_rectangle")
    asyncio.run(
        create_rectangle(
            x_mm=0, y_mm=0, width_mm=10, height_mm=10,
            mode="auto",
        )
    )
    body = patched_shapes.last_script_body
    # No styling args → no setFillColor / setLineColor in the body.
    assert "_s.createRect" in body
    assert "setFillColor" not in body
    assert "setLineColor" not in body


def test_create_rectangle_palette_role_resolves(patched_shapes):
    """Pass a role name that's defined in the document — resolver should
    let it pass through. (Brand stands in for any role.)"""
    create_rectangle = _build_tool("create_rectangle")
    asyncio.run(
        create_rectangle(
            x_mm=0, y_mm=0, width_mm=10, height_mm=10,
            fill_color="Brand",
            mode="auto",
        )
    )
    assert "_s.setFillColor('Brand', _v)" in patched_shapes.last_script_body


def test_create_rectangle_role_falls_back_to_black(patched_shapes):
    """Pass an undefined role — resolver falls back to ``"Black"``."""
    create_rectangle = _build_tool("create_rectangle")
    asyncio.run(
        create_rectangle(
            x_mm=0, y_mm=0, width_mm=10, height_mm=10,
            fill_color="primary",  # not in the mock's defined colors
            mode="auto",
        )
    )
    assert "_s.setFillColor('Black', _v)" in patched_shapes.last_script_body


def test_create_ellipse_accepts_fill_and_line(patched_shapes):
    create_ellipse = _build_tool("create_ellipse")
    asyncio.run(
        create_ellipse(
            x_mm=0, y_mm=0, width_mm=20, height_mm=20,
            fill_color="Brand",
            line_color="None",
            mode="auto",
        )
    )
    body = patched_shapes.last_script_body
    assert "_s.createEllipse(0, 0, 20, 20)" in body
    assert "_s.setFillColor('Brand', _v)" in body
    assert '_s.setLineColor("None", _v)' in body


def test_create_line_accepts_line_args(patched_shapes):
    create_line = _build_tool("create_line")
    asyncio.run(
        create_line(
            x1_mm=0, y1_mm=0, x2_mm=100, y2_mm=0,
            line_color="Brand",
            line_width_pt=1.4,
            mode="auto",
        )
    )
    body = patched_shapes.last_script_body
    assert "_s.createLine" in body
    assert "_s.setLineColor('Brand', _v)" in body
    assert "_s.setLineWidth(1.4, _v)" in body


def test_create_polygon_accepts_styling(patched_shapes):
    create_polygon = _build_tool("create_polygon")
    asyncio.run(
        create_polygon(
            points_mm=[0, 0, 10, 0, 5, 10],
            fill_color="Brand",
            line_color="None",
            mode="auto",
        )
    )
    body = patched_shapes.last_script_body
    assert "_s.createPolygon" in body
    assert "_s.setFillColor('Brand', _v)" in body
    assert '_s.setLineColor("None", _v)' in body

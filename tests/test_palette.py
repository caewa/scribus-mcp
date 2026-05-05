"""Palette resolver — role-named colors fall through to defined palette
colors, fall back to ``"Black"`` when the role isn't defined, and respect
explicit shade overrides from the caller.
"""

from __future__ import annotations

import asyncio

import pytest

from scribus_mcp.backends.base import ScribusBackend, ScribusResult
from scribus_mcp.tools.palette import (
    ROLE_NAMES,
    add_known_color,
    invalidate_palette,
    resolve_color,
)


class _Backend(ScribusBackend):
    """Minimal backend that returns a fixed list from ``getColorNames``."""

    def __init__(self, colors=()):
        self._colors = list(colors)
        self.color_probe_count = 0

    async def is_available(self) -> bool:
        return True

    async def call(self, method, *args, **kwargs):
        if method == "getColorNames":
            self.color_probe_count += 1
            return ScribusResult(ok=True, value=list(self._colors))
        return ScribusResult(ok=True, value=None)

    async def script(self, body, result_expr="None"):
        return ScribusResult(ok=True, value=None)


@pytest.fixture(autouse=True)
def _clear_palette_cache():
    invalidate_palette(None)
    yield
    invalidate_palette(None)


def test_role_resolves_to_defined_palette_color():
    backend = _Backend(colors=["primary", "accent", "Black"])
    name, shade = asyncio.run(resolve_color(backend, "primary"))
    assert name == "primary"
    # role_shade default is 100 since the caller didn't pass current_shade
    assert shade == 100


def test_role_falls_back_to_black_when_undefined():
    backend = _Backend(colors=["Black"])
    name, shade = asyncio.run(
        resolve_color(backend, "primary", fallback_shade=8)
    )
    assert name == "Black"
    assert shade == 8


def test_explicit_current_shade_wins_over_role_shade():
    backend = _Backend(colors=["primary"])
    name, shade = asyncio.run(
        resolve_color(backend, "primary", current_shade=42)
    )
    assert name == "primary"
    # caller passed shade=42 explicitly — resolver must respect it
    assert shade == 42


def test_explicit_current_shade_wins_over_fallback_shade():
    backend = _Backend(colors=["Black"])
    name, shade = asyncio.run(
        resolve_color(backend, "primary", fallback_shade=8, current_shade=42),
    )
    assert name == "Black"
    assert shade == 42


def test_literal_color_passes_through_when_defined():
    backend = _Backend(colors=["Z Cyan", "Black"])
    name, shade = asyncio.run(resolve_color(backend, "Z Cyan"))
    assert name == "Z Cyan"
    assert shade == 100


def test_unknown_literal_falls_back_to_black():
    backend = _Backend(colors=["Black"])
    name, shade = asyncio.run(resolve_color(backend, "Z Cyan", fallback_shade=50))
    assert name == "Black"
    assert shade == 50


def test_empty_name_uses_fallback():
    backend = _Backend(colors=["primary"])
    name, shade = asyncio.run(resolve_color(backend, "", fallback_shade=20))
    assert name == "Black"
    assert shade == 20


def test_caching_avoids_repeat_probes():
    backend = _Backend(colors=["primary", "accent", "Black"])

    async def two_lookups():
        await resolve_color(backend, "primary")
        await resolve_color(backend, "accent")
        await resolve_color(backend, "ink")  # not defined

    asyncio.run(two_lookups())
    # All three resolutions share the same probed list.
    assert backend.color_probe_count == 1


def test_add_known_color_seeds_cache_without_probe():
    backend = _Backend(colors=["Black"])

    async def flow():
        # Prime cache with a probe.
        await resolve_color(backend, "Black")
        # Pretend define_color_rgb just succeeded.
        add_known_color(backend, "primary")
        # Resolve should now see "primary" without re-probing.
        name, _ = await resolve_color(backend, "primary")
        return name

    name = asyncio.run(flow())
    assert name == "primary"
    assert backend.color_probe_count == 1  # only the initial prime


def test_invalidate_drops_cache():
    backend = _Backend(colors=["primary"])

    async def flow():
        await resolve_color(backend, "primary")  # probe 1
        invalidate_palette(backend)
        await resolve_color(backend, "primary")  # probe 2 (cache cleared)

    asyncio.run(flow())
    assert backend.color_probe_count == 2


def test_role_names_is_frozen_set():
    # Stable contract: tools default to one of these role strings; the
    # set is the public contract for the colors module / docs.
    assert "primary" in ROLE_NAMES
    assert "accent" in ROLE_NAMES
    assert "surface" in ROLE_NAMES
    assert "ink" in ROLE_NAMES
    assert "muted" in ROLE_NAMES

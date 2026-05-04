"""Unit tests for the runtime Scribus version gate.

Covers ``get_scribus_version`` (probe + caching) and
``require_min_scribus_version`` (structured payload returned to the MCP
client when the running Scribus is too old).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from scribus_mcp.backends.base import ScribusResult
from scribus_mcp.tools import _common
from scribus_mcp.tools._common import (
    get_scribus_version,
    require_min_scribus_version,
)


@dataclass
class FakeBackend:
    """Stand-in for a real backend; records script calls + canned responses."""

    response: ScribusResult
    calls: list[str]

    async def script(self, body: str, result_expr: str = "None") -> ScribusResult:
        self.calls.append(body)
        return self.response

    async def call(self, *args: Any, **kwargs: Any) -> ScribusResult:  # pragma: no cover
        raise NotImplementedError


def _ok(value: list) -> ScribusResult:
    return ScribusResult(ok=True, value=value, error=None, traceback=None)


def _fail(error: str) -> ScribusResult:
    return ScribusResult(ok=False, value=None, error=error, traceback=None)


@pytest.fixture(autouse=True)
def _clear_cache():
    _common._VERSION_CACHE.clear()
    yield
    _common._VERSION_CACHE.clear()


@pytest.mark.asyncio
async def test_get_scribus_version_returns_tuple_from_probe():
    backend = FakeBackend(response=_ok([1, 7, 3]), calls=[])
    assert await get_scribus_version(backend) == (1, 7, 3)
    assert len(backend.calls) == 1
    assert "scribus_version_info" in backend.calls[0]


@pytest.mark.asyncio
async def test_get_scribus_version_caches_per_backend():
    backend = FakeBackend(response=_ok([1, 6, 3]), calls=[])
    assert await get_scribus_version(backend) == (1, 6, 3)
    assert await get_scribus_version(backend) == (1, 6, 3)
    # Single probe even after multiple calls.
    assert len(backend.calls) == 1


@pytest.mark.asyncio
async def test_get_scribus_version_returns_zero_on_failure():
    backend = FakeBackend(response=_fail("bridge unreachable"), calls=[])
    assert await get_scribus_version(backend) == (0, 0, 0)


@pytest.mark.asyncio
async def test_get_scribus_version_returns_zero_on_short_payload():
    backend = FakeBackend(response=_ok([1]), calls=[])
    assert await get_scribus_version(backend) == (0, 0, 0)


@pytest.mark.asyncio
async def test_require_min_passes_when_version_meets_floor():
    backend = FakeBackend(response=_ok([1, 7, 3]), calls=[])
    gate = await require_min_scribus_version(
        backend, feature="x", required=(1, 7, 0)
    )
    assert gate is None


@pytest.mark.asyncio
async def test_require_min_blocks_with_structured_payload():
    backend = FakeBackend(response=_ok([1, 6, 3]), calls=[])
    gate = await require_min_scribus_version(
        backend, feature="create_qr_code_block", required=(1, 7, 0)
    )
    assert gate is not None
    assert gate["ok"] is False
    assert gate["required_version"] == "1.7.0"
    assert gate["actual_version"] == "1.6.3"
    assert "create_qr_code_block" in gate["error"]
    assert "1.7.0" in gate["error"]
    assert "1.6.3" in gate["error"]


@pytest.mark.asyncio
async def test_require_min_reports_unknown_when_probe_fails():
    backend = FakeBackend(response=_fail("nope"), calls=[])
    gate = await require_min_scribus_version(
        backend, feature="x", required=(1, 7, 0)
    )
    assert gate is not None
    assert gate["actual_version"] == "unknown"


@pytest.mark.asyncio
async def test_require_min_at_exact_floor_passes():
    backend = FakeBackend(response=_ok([1, 7, 0]), calls=[])
    gate = await require_min_scribus_version(
        backend, feature="x", required=(1, 7, 0)
    )
    assert gate is None

"""Helpers for caller-side scripts that drive the MCP via FastMCP's
``call_tool`` API directly (instead of via stdio/HTTP transport).

These are convenience utilities for the demo scripts and integration
tests — they're not part of the MCP wire protocol. Keep this module
small and dependency-free so anyone writing automation against the
in-process server can ``from scribus_mcp.testing import unwrap``.
"""

from __future__ import annotations

import json
from typing import Any


def unwrap(out: Any) -> dict | list | Any:
    """Convert a FastMCP ``call_tool`` return value into a plain dict.

    FastMCP's ``call_tool`` returns either:

    - a list of ``TextContent`` / ``ImageContent`` objects (legacy shape)
    - a ``(content_list, structured_dict)`` tuple (newer shape with
      structured output)

    Both shapes are messy to consume directly. This helper normalises:

    - tuple → returns the structured dict if present, else recurses
    - list of TextContent → parses the JSON in the first item's ``.text``
    - anything else → returned as-is
    - JSON parse failure → ``{"raw": <original text>}`` so the caller
      can inspect the raw body without crashing.
    """
    if isinstance(out, tuple) and len(out) == 2:
        content, structured = out
        if structured:
            return structured
        return unwrap(content)
    if isinstance(out, list) and out:
        first = out[0]
        text = getattr(first, "text", None) or str(first)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
    return out


__all__ = ["unwrap"]

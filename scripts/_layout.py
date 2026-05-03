"""Backward-compat shim — the canonical home is :mod:`scribus_mcp.layout`.

Kept so older copies of the demo scripts (or third-party scripts that
imported from here) still work. New code should
``from scribus_mcp.layout import PageCursor`` directly.
"""

from scribus_mcp.layout import PageCursor

__all__ = ["PageCursor"]

"""Group created objects into a single Scribus group.

Used by every multi-element pattern/layout so callers can move,
scale or delete the whole feature as one unit instead of selecting
each piece individually.
"""

from __future__ import annotations

from scribus_mcp.backends.base import ScribusBackend


async def group_created_objects(
    backend: ScribusBackend, names: list[str | None]
) -> str | None:
    """Group ``names`` and return the Scribus name of the new group.

    Filters out ``None``/empty entries. Returns ``None`` when nothing is
    groupable (zero objects), or the lone object name when exactly one
    is present (no group needed). Errors are swallowed: grouping is a
    nice-to-have and shouldn't break feature creation if Scribus
    rejects a particular member combination.
    """
    flat = [n for n in names if n]
    if not flat:
        return None
    if len(flat) == 1:
        return flat[0]
    body = (
        "import scribus as _s\n"
        f"_names = {flat!r}\n"
        "_before = set(_it[0] for _it in (_s.getPageItems() or []))\n"
        "try:\n"
        "    _s.groupObjects(_names)\n"
        "except Exception:\n"
        "    _value = None\n"
        "else:\n"
        "    _after = set(_it[0] for _it in (_s.getPageItems() or []))\n"
        "    _new = sorted(_after - _before - set(_names))\n"
        "    _value = _new[-1] if _new else None\n"
    )
    res = await backend.script(body, result_expr="_value")
    return res.value if res.ok else None

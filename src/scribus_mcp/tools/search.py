from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

# Scripter does not expose a native find_text/replace_text. We build it
# from getAllText / setText scoped to a frame, or iterate page items.

_FIND_REPLACE_BODY = """\
import scribus as _s
_target = {target!r}
_replacement = {replacement!r}
_scope = {scope!r}  # 'frame' | 'page' | 'document'
_frame_name = {frame_name!r}
_replacements = 0

def _process_frame(_n):
    global _replacements
    try:
        _txt = _s.getAllText(_n)
    except Exception:
        return
    if _target not in _txt:
        return
    _new = _txt.replace(_target, _replacement)
    _replacements += _txt.count(_target)
    _s.setText(_new, _n)

if _scope == 'frame':
    if _frame_name:
        _process_frame(_frame_name)
elif _scope == 'page':
    for _item in (_s.getPageItems() or []):
        if isinstance(_item, (list, tuple)) and len(_item) >= 2 and _item[1] == 4:
            _process_frame(_item[0])
elif _scope == 'document':
    _orig = _s.currentPage()
    for _p in range(1, _s.pageCount() + 1):
        _s.gotoPage(_p)
        for _item in (_s.getPageItems() or []):
            if isinstance(_item, (list, tuple)) and len(_item) >= 2 and _item[1] == 4:
                _process_frame(_item[0])
    _s.gotoPage(_orig)

_value = _replacements
"""


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def find_and_replace_text(
        target: str,
        replacement: str,
        scope: str = "document",
        frame_name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Replace all occurrences of `target` with `replacement`.

        scope: 'frame' (requires frame_name), 'page' (current page only), 'document' (all pages).
        Returns the number of replacements made.
        """
        if scope not in ("frame", "page", "document"):
            return {"ok": False, "error": "scope must be one of: frame, page, document"}
        if scope == "frame" and not frame_name:
            return {"ok": False, "error": "frame_name is required when scope='frame'"}
        backend = await get_backend(ctx, mode)
        body = _FIND_REPLACE_BODY.format(
            target=target, replacement=replacement, scope=scope, frame_name=frame_name
        )
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "replacements": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def find_objects(
        object_type: str = "",
        page_number: int = 0,
        layer: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Find objects matching a filter.

        - ``object_type``: ``text`` | ``image`` | ``line`` | ``polygon``
          | ``polyline`` | ``group``. Empty string matches any type.
        - ``page_number``: 0 means current page; otherwise an absolute
          1-indexed page.
        - ``layer``: **not currently supported** — Scribus 1.7's
          ``getProperty(name, 'layer')`` doesn't reliably return the
          layer name across builds, so any ``layer`` value would
          either silently filter to nothing or throw. The tool returns
          a clean error when set so callers know to inspect ``layer``
          another way (e.g. set the layer active first via
          ``set_active_layer`` and re-run with ``layer=""``).
        """
        if layer:
            return {
                "ok": False,
                "error": (
                    "layer filter is not supported in Scribus 1.7's Scripter API "
                    "(getProperty(name, 'layer') is unreliable). Use "
                    "set_active_layer first, then call find_objects with layer=''."
                ),
                "objects": [],
            }
        type_map = {
            "image": 2,
            "line": 3,
            "text": 4,
            "polygon": 6,
            "polyline": 7,
            "group": 12,
        }
        body = f"""\
import scribus as _s
_results = []
_filter_type = {type_map.get(object_type, -1)}
_pages = [{page_number}] if {page_number} > 0 else list(range(1, _s.pageCount() + 1))
_orig = _s.currentPage()
for _p in _pages:
    _s.gotoPage(_p)
    for _item in (_s.getPageItems() or []):
        if not isinstance(_item, (list, tuple)) or len(_item) < 2:
            continue
        _name, _t = _item[0], _item[1]
        if _filter_type != -1 and _t != _filter_type:
            continue
        _results.append({{'name': _name, 'type': _t, 'page': _p}})
_s.gotoPage(_orig)
_value = _results
"""
        backend = await get_backend(ctx, mode)
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "objects": result.unwrap_or(), "error": result.error}

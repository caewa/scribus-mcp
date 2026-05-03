from __future__ import annotations

import json

from scribus_mcp.tools._common import ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.resource("scribus://document/info")
    async def document_info() -> str:
        """Current document path, page count, dimensions, units. Empty if no doc open."""
        backend = await get_backend(ctx, "auto")
        if not await backend.is_available():
            return json.dumps({"available": False, "reason": "no backend ready"})
        body = (
            "import scribus as _s\n"
            "if not _s.haveDoc():\n"
            "    _value = {'has_doc': False}\n"
            "else:\n"
            "    _value = {\n"
            "        'has_doc': True,\n"
            "        'path': _s.getDocName(),\n"
            "        'page_count': _s.pageCount(),\n"
            "        'page_size': _s.getPageSize(),\n"
            "        'unit': _s.getUnit(),\n"
            "        'current_page': _s.currentPage(),\n"
            "    }"
        )
        result = await backend.script(body, result_expr="_value")
        return json.dumps(result.value if result.ok else {"error": result.error})

    @mcp.resource("scribus://document/colors")
    async def document_colors() -> str:
        """Names of all colors defined in the current document."""
        backend = await get_backend(ctx, "auto")
        result = await backend.call("getColorNames")
        return json.dumps(result.value if result.ok else {"error": result.error})

    @mcp.resource("scribus://document/fonts")
    async def document_fonts() -> str:
        """Fonts available to Scribus (system-wide), and fonts used in the doc."""
        backend = await get_backend(ctx, "auto")
        body = """\
import scribus as _s
_used = set()
try:
    if _s.haveDoc():
        for _p in range(1, _s.pageCount() + 1):
            _s.gotoPage(_p)
            for _item in (_s.getPageItems() or []):
                if isinstance(_item, (list, tuple)) and len(_item) >= 2 and _item[1] == 4:
                    try:
                        _used.add(_s.getFont(_item[0]))
                    except Exception:
                        pass
except Exception:
    pass
_available = []
try:
    _available = list(_s.getFontNames()) if hasattr(_s, 'getFontNames') else []
except Exception:
    _available = []
_value = {'used': sorted(_used), 'available': _available}
"""
        result = await backend.script(body, result_expr="_value")
        return json.dumps(result.value if result.ok else {"error": result.error})

    @mcp.resource("scribus://document/missing-resources")
    async def missing_resources() -> str:
        """List images and fonts referenced by the doc but missing on disk / system."""
        backend = await get_backend(ctx, "auto")
        body = """\
import os
import scribus as _s
_missing_images = []
_missing_fonts = []
try:
    _avail_fonts = set(_s.getFontNames()) if hasattr(_s, 'getFontNames') else set()
    if _s.haveDoc():
        for _p in range(1, _s.pageCount() + 1):
            _s.gotoPage(_p)
            for _item in (_s.getPageItems() or []):
                if not isinstance(_item, (list, tuple)) or len(_item) < 2:
                    continue
                _n, _t = _item[0], _item[1]
                if _t == 2:  # image
                    try:
                        _f = _s.getImageFile(_n)
                        if _f and not os.path.exists(_f):
                            _missing_images.append({'object': _n, 'path': _f, 'page': _p})
                    except Exception:
                        pass
                if _t == 4:  # text
                    try:
                        _font = _s.getFont(_n)
                        if _avail_fonts and _font not in _avail_fonts:
                            _missing_fonts.append({'object': _n, 'font': _font, 'page': _p})
                    except Exception:
                        pass
except Exception as exc:
    _missing_images = [{'error': str(exc)}]
_value = {'images': _missing_images, 'fonts': _missing_fonts}
"""
        result = await backend.script(body, result_expr="_value")
        return json.dumps(result.value if result.ok else {"error": result.error})

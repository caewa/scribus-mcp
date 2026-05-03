from __future__ import annotations

import base64
import contextlib
from pathlib import Path
from typing import Annotated

from mcp.types import ImageContent, TextContent
from pydantic import Field

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def export_pdf(
        path: str,
        pages: str = "all",
        resolution: Annotated[int, Field(ge=72, le=2400)] = 300,
        compress: bool = True,
        version: Annotated[str, Field(pattern="^(1\\.4|1\\.5|X-1a|X-3|X-4)$")] = "1.5",
        bleed_mm: float = 0.0,
        mode: Mode = "auto",
    ) -> dict:
        """Export the document to PDF.

        pages='all' or a comma list like '1,3,5-7'. version: 1.4 | 1.5 | X-1a | X-3 | X-4.
        """
        version_map = {"1.4": 13, "1.5": 14, "X-1a": 11, "X-3": 12, "X-4": 15}
        body = f"""\
import scribus as _s
_pdf = _s.PDFfile()
_pdf.file = {path!r}
_pdf.compress = {1 if compress else 0}
_pdf.compressmtd = 0
_pdf.version = {version_map[version]}
_pdf.resolution = {resolution}
_pdf.bleedt = {bleed_mm}
_pdf.bleedb = {bleed_mm}
_pdf.bleedl = {bleed_mm}
_pdf.bleedr = {bleed_mm}
_total = _s.pageCount()
if {pages!r} == 'all':
    _pdf.pages = list(range(1, _total + 1))
else:
    _ranges = []
    for _part in {pages!r}.split(','):
        _part = _part.strip()
        if '-' in _part:
            _a, _b = _part.split('-', 1)
            _ranges.extend(range(int(_a), int(_b) + 1))
        elif _part:
            _ranges.append(int(_part))
    _pdf.pages = _ranges
_pdf.save()
_value = {{'path': {path!r}, 'pages_exported': len(_pdf.pages)}}
"""
        backend = await get_backend(ctx, mode)
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

    @mcp.tool()
    async def render_page_to_image(
        page_number: int = 0,
        dpi: Annotated[int, Field(ge=36, le=600)] = 144,
        max_pixels: Annotated[int, Field(ge=256, le=8192)] = 2048,
        mode: Mode = "auto",
    ) -> list[TextContent | ImageContent]:
        """Render a page to a PNG and return it inline so Claude can see the layout.

        page_number=0 means the current page. The image is downscaled so
        max(width, height) <= max_pixels to keep responses small.
        """
        out_path = ctx.config.workdir / f"render-{page_number or 'current'}.png"
        body = f"""\
import scribus as _s
_pn = {page_number}
if _pn > 0:
    _s.gotoPage(_pn)
_s.saveAsImage = getattr(_s, 'saveAsImage', None)
# Use ImageExport for current page.
_export = _s.ImageExport() if hasattr(_s, 'ImageExport') else None
if _export is None:
    raise RuntimeError('ImageExport API unavailable in this Scribus build')
_export.type = 'PNG'
_export.dpi = {dpi}
_export.scale = 100
_export.transparentBkgnd = 0
_export.quality = 100
_export.saveAs({str(out_path)!r})
_value = {str(out_path)!r}
"""
        backend = await get_backend(ctx, mode)
        result = await backend.script(body, result_expr="_value")
        if not result.ok:
            return [TextContent(type="text", text=f"Render failed: {result.error}")]

        png_path = Path(out_path)
        if not png_path.exists():
            return [TextContent(type="text", text=f"Render failed: {out_path} not produced")]

        try:
            from PIL import Image

            img = Image.open(png_path)
            w, h = img.size
            biggest = max(w, h)
            if biggest > max_pixels:
                scale = max_pixels / biggest
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            from io import BytesIO

            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            data = buf.getvalue()
        except ImportError:
            data = png_path.read_bytes()
        finally:
            with contextlib.suppress(OSError):
                png_path.unlink()

        encoded = base64.b64encode(data).decode("ascii")
        return [
            TextContent(type="text", text=f"Rendered page {page_number or 'current'} at {dpi} DPI"),
            ImageContent(type="image", data=encoded, mimeType="image/png"),
        ]

    @mcp.tool()
    async def preflight_check(mode: Mode = "auto") -> dict:
        """Run Scribus's preflight verifier and return categorized issues."""
        body = """\
import scribus as _s
_issues = []
# Iterate doc and collect basic issues we can detect from Scripter.
try:
    _fonts = set()
    for _p in range(1, _s.pageCount() + 1):
        _s.gotoPage(_p)
        for _item in (_s.getPageItems() or []):
            if not isinstance(_item, (list, tuple)) or len(_item) < 2:
                continue
            _n, _t = _item[0], _item[1]
            if _t == 4:  # text
                try:
                    if _s.textOverflows(_n):
                        _issues.append({'severity': 'error', 'kind': 'text_overflow', 'object': _n, 'page': _p})
                except Exception:
                    pass
                try:
                    _fonts.add(_s.getFont(_n))
                except Exception:
                    pass
            if _t == 2:  # image
                try:
                    _f = _s.getImageFile(_n)
                    if _f and not _f.startswith('embedded'):
                        import os as _os
                        if _f and not _os.path.exists(_f):
                            _issues.append({'severity': 'error', 'kind': 'missing_image', 'object': _n, 'page': _p, 'path': _f})
                except Exception:
                    pass
    _value = {'issues': _issues, 'used_fonts': sorted(_fonts)}
except Exception as exc:
    _value = {'issues': [{'severity': 'error', 'kind': 'preflight_failed', 'message': str(exc)}], 'used_fonts': []}
"""
        backend = await get_backend(ctx, mode)
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "report": result.unwrap_or(), "error": result.error}

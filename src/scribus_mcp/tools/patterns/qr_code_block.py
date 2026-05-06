"""QR / barcode block via Scribus's BWIPP backend, with optional caption."""

from __future__ import annotations

from scribus_mcp.tools._common import (
    Mode,
    ServerCtx,
    clean_user_text,
    get_backend,
    require_min_scribus_version,
)
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_qr_code_block(
        data: str,
        x_mm: float,
        y_mm: float,
        size_mm: float = 30.0,
        encoder: str = "qrcode",
        options: str = "eclevel=H",
        caption: str = "",
        caption_color: str = "muted",
        caption_font_size_pt: float = 7.5,
        mode: Mode = "auto",
    ) -> dict:
        """Generate a barcode (QR by default) and place it on the page,
        optionally with a small caption underneath.

        ``encoder`` is a BWIPP encoder name — common values: ``qrcode``,
        ``ean13``, ``code128``, ``datamatrix``, ``code39``.

        Requires Scribus 1.7.0+ (``scribus.createBarcode`` was added there)
        and Ghostscript on the host (Scribus's barcode plugin shells out
        to it). Returns ``ok=False`` with a ``required_version`` /
        ``actual_version`` payload if Scribus is too old, or with the
        underlying error if Ghostscript is missing.

        Single-script-body design (one round-trip vs the previous five).
        """
        backend = await get_backend(ctx, mode)
        gate = await require_min_scribus_version(
            backend,
            feature="create_qr_code_block (scribus.createBarcode)",
            required=(1, 7, 0),
        )
        if gate is not None:
            return gate

        caption_color, _ = await resolve_color(backend, caption_color)
        cap_h = max(4.0, caption_font_size_pt * 0.5 + 1.5)
        caption = clean_user_text(caption)
        body = f"""
import scribus as _s

_barcode = _s.createBarcode({encoder!r}, {data!r}, {options!r}, {x_mm}, {y_mm})
_s.sizeObject({size_mm}, {size_mm}, _barcode)

_caption = None
if {caption!r}:
    _caption = _s.createText({x_mm}, {y_mm + size_mm + 1}, {size_mm}, {cap_h})
    _s.setText({caption!r}, _caption)
    _s.setFontSize({float(caption_font_size_pt)}, _caption)
    _s.setTextColor({caption_color!r}, _caption)
    _s.setTextAlignment(1, _caption)

_value = {{"barcode": _barcode, "caption": _caption}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "createBarcode failed"}
        out = res.value or {}
        group_name = await group_created_objects(
            backend, [out.get("barcode"), out.get("caption")]
        )
        return {
            "ok": True,
            "barcode": out.get("barcode"),
            "caption": out.get("caption"),
            "group": group_name,
            "error": None,
        }

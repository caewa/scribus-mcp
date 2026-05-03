"""QR / barcode block via Scribus's BWIPP backend, with optional caption."""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


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
        caption_color: str = "Black",
        caption_font_size_pt: float = 7.5,
        mode: Mode = "auto",
    ) -> dict:
        """Generate a barcode (QR by default) and place it on the page,
        optionally with a small caption underneath.

        ``encoder`` is a BWIPP encoder name — common values: ``qrcode``,
        ``ean13``, ``code128``, ``datamatrix``, ``code39``.

        Requires Ghostscript on the host (Scribus's barcode plugin shells out
        to it). Returns ``ok=False`` with the underlying error if Ghostscript
        is missing.

        Single-script-body design (one round-trip vs the previous five).
        """
        cap_h = max(4.0, caption_font_size_pt * 0.5 + 1.5)
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

        backend = await get_backend(ctx, mode)
        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "createBarcode failed"}
        out = res.value or {}
        return {
            "ok": True,
            "barcode": out.get("barcode"),
            "caption": out.get("caption"),
            "error": None,
        }

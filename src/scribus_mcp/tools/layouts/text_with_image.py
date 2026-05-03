"""Two-column layout: image frame + text frame side by side."""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_text_with_image(
        text: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        image_path: str = "",
        image_side: str = "left",
        image_ratio: float = 0.4,
        gap_mm: float = 6.0,
        font_size_pt: float = 10.0,
        text_color: str = "Black",
        alignment: str = "justify",
        line_spacing_pt: float = 13.0,
        scale_image_to_frame: bool = True,
        proportional: bool = True,
        mode: Mode = "auto",
    ) -> dict:
        """Image frame + text frame inside (x, y, width, height).

        ``image_side`` ∈ {"left", "right"} determines which side hosts the image.
        ``image_ratio`` is the image column's fraction of width (after the gap),
        in (0, 1). 0.4 = image column 40% of available width, text 60%.

        If ``image_path`` is given (and the file exists), it's loaded into the
        image frame and (by default) scaled to fit. Otherwise the frame is left
        empty for the caller to fill with ``load_image`` later.
        """
        if image_side not in ("left", "right"):
            return {"ok": False, "error": "image_side must be 'left' or 'right'"}
        if not 0 < image_ratio < 1:
            return {"ok": False, "error": "image_ratio must be in (0, 1)"}
        align_map = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}
        if alignment not in align_map:
            return {"ok": False, "error": f"alignment must be one of {sorted(align_map)}"}

        backend = await get_backend(ctx, mode)
        avail = width_mm - gap_mm
        img_w = avail * image_ratio
        text_w = avail - img_w

        if image_side == "left":
            img_x = x_mm
            text_x = x_mm + img_w + gap_mm
        else:
            text_x = x_mm
            img_x = x_mm + text_w + gap_mm

        # Image frame
        ir = await backend.call("createImage", img_x, y_mm, img_w, height_mm)
        if not ir.ok:
            return {"ok": False, "error": f"image frame failed: {ir.error}"}
        in_ = ir.value
        if image_path:
            li = await backend.call("loadImage", image_path, in_)
            if li.ok and scale_image_to_frame:
                await backend.call("setScaleImageToFrame", 1, 1 if proportional else 0, in_)

        # Text frame
        tr = await backend.call("createText", text_x, y_mm, text_w, height_mm)
        if not tr.ok:
            return {"ok": False, "error": f"text frame failed: {tr.error}", "image": in_}
        tn = tr.value
        await backend.call("setText", text, tn)
        await backend.call("setFontSize", float(font_size_pt), tn)
        await backend.call("setTextColor", text_color, tn)
        await backend.call("setTextAlignment", align_map[alignment], tn)
        await backend.call("setLineSpacing", float(line_spacing_pt), tn)

        return {
            "ok": True,
            "image": in_,
            "text": tn,
            "image_width_mm": img_w,
            "text_width_mm": text_w,
            "error": None,
        }

"""Image frame with a figure-style caption underneath, optionally numbered."""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_image_caption(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        caption: str = "",
        image_path: str = "",
        figure_number: int = 0,
        figure_prefix: str = "Figure",
        scale_image_to_frame: bool = True,
        proportional: bool = True,
        caption_height_mm: float = 8.0,
        caption_gap_mm: float = 1.0,
        caption_color: str = "muted",
        caption_font_size_pt: float = 8.0,
        caption_alignment: str = "left",
        figure_label_color: str = "accent",
        mode: Mode = "auto",
    ) -> dict:
        """Image frame plus a caption underneath. The image takes
        ``height_mm - caption_height_mm - caption_gap_mm`` of vertical space.

        If ``figure_number`` > 0, the caption is prefixed with
        ``"<figure_prefix> <n>. "`` (e.g. ``"Figure 1. The architecture"``)
        rendered in a slightly bolder color (``figure_label_color``) for the
        prefix and ``caption_color`` for the rest.

        ``image_path`` is optional — leave empty to leave the image frame
        ready for ``load_image`` later.
        """
        align_map = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}
        if caption_alignment not in align_map:
            return {"ok": False, "error": f"caption_alignment must be one of {sorted(align_map)}"}
        if caption_height_mm + caption_gap_mm >= height_mm:
            return {"ok": False, "error": "height_mm too small for caption + gap"}

        backend = await get_backend(ctx, mode)
        caption_color, _ = await resolve_color(backend, caption_color)
        figure_label_color, _ = await resolve_color(backend, figure_label_color)
        caption = clean_user_text(caption)
        img_h = height_mm - caption_height_mm - caption_gap_mm

        # Image frame
        ir = await backend.call("createImage", x_mm, y_mm, width_mm, img_h)
        if not ir.ok:
            return {"ok": False, "error": f"image frame failed: {ir.error}"}
        in_ = ir.value
        if image_path:
            li = await backend.call("loadImage", image_path, in_)
            if li.ok and scale_image_to_frame:
                await backend.call("setScaleImageToFrame", 1, 1 if proportional else 0, in_)

        # Caption
        cap_y = y_mm + img_h + caption_gap_mm
        cr = await backend.call("createText", x_mm, cap_y, width_mm, caption_height_mm)
        if not cr.ok:
            return {"ok": False, "error": f"caption failed: {cr.error}", "image": in_}
        cn = cr.value

        if figure_number > 0:
            label = f"{figure_prefix} {figure_number}. "
            full_text = label + caption
            await backend.call("setText", full_text, cn)
            # Style the prefix in the figure_label_color, rest in caption_color.
            # Scribus's selectText + setTextColor scope colour changes to a range.
            await backend.call("selectText", 0, len(label), cn)
            await backend.call("setTextColor", figure_label_color, cn)
            await backend.call("selectText", len(label), len(caption), cn)
            await backend.call("setTextColor", caption_color, cn)
        else:
            await backend.call("setText", caption, cn)
            await backend.call("setTextColor", caption_color, cn)

        await backend.call("setFontSize", float(caption_font_size_pt), cn)
        await backend.call("setTextAlignment", align_map[caption_alignment], cn)

        group_name = await group_created_objects(backend, [in_, cn])
        return {
            "ok": True,
            "image": in_,
            "caption": cn,
            "group": group_name,
            "image_height_mm": img_h,
            "figure_number": figure_number if figure_number > 0 else None,
            "error": None,
        }

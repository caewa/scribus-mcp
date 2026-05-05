"""Full-width colored band with title + optional subtitle / eyebrow overlay."""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_hero_band(
        title: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 28.0,
        fill_color: str = "primary",
        fill_shade: int | None = None,
        title_color: str = "White",
        title_font_size_pt: float = 22.0,
        subtitle: str = "",
        subtitle_color: str = "White",
        subtitle_font_size_pt: float = 9.0,
        eyebrow: str = "",
        eyebrow_color: str = "White",
        eyebrow_font_size_pt: float = 7.0,
        right_text: str = "",
        right_color: str = "White",
        right_font_size_pt: float = 8.0,
        padding_x_mm: float = 12.0,
        padding_y_mm: float = 6.0,
        mode: Mode = "auto",
    ) -> dict:
        """A full-width colored band with overlay text. Used as page openers
        or section transitions.

        Layout (vertical):
            optional eyebrow (small caps) — top-left
            title (large) — main
            optional subtitle (small) — under title

        Plus optional ``right_text`` (small) anchored to the band's right
        edge, useful for version / date / context labels in the page chrome.

        ``fill_color`` defaults to the palette role ``primary`` — define
        it with ``define_color_rgb`` and every hero band picks up the
        brand color. Title / subtitle / eyebrow / right text default to
        ``"White"`` for contrast on the dark band; resolution still
        accepts palette role names if you want to override.
        """
        backend = await get_backend(ctx, mode)
        fill_color, fill_shade = await resolve_color(
            backend, fill_color, fallback_shade=100, current_shade=fill_shade,
        )
        title_color, _ = await resolve_color(backend, title_color, fallback_color="White")
        subtitle_color, _ = await resolve_color(backend, subtitle_color, fallback_color="White")
        eyebrow_color, _ = await resolve_color(backend, eyebrow_color, fallback_color="White")
        right_color, _ = await resolve_color(backend, right_color, fallback_color="White")

        # Background band
        br = await backend.call("createRect", x_mm, y_mm, width_mm, height_mm)
        if not br.ok:
            return {"ok": False, "error": f"band failed: {br.error}"}
        band = br.value
        await backend.call("setFillColor", fill_color, band)
        if fill_shade != 100:
            await backend.call("setFillShade", int(fill_shade), band)
        await backend.call("setLineColor", "None", band)

        eyebrow_name: str | None = None
        title_name: str | None = None
        subtitle_name: str | None = None
        right_name: str | None = None

        title = clean_user_text(title)
        eyebrow = clean_user_text(eyebrow)
        subtitle = clean_user_text(subtitle)
        right_text = clean_user_text(right_text)

        cur_y = y_mm + padding_y_mm
        text_w = width_mm - 2 * padding_x_mm
        right_w = 0.0
        if right_text:
            right_w = max(40.0, text_w * 0.35)
            text_w -= right_w + 2

        # Eyebrow
        if eyebrow:
            er = await backend.call("createText", x_mm + padding_x_mm, cur_y, text_w, 4)
            if er.ok:
                eyebrow_name = er.value
                await backend.call("setText", eyebrow.upper(), eyebrow_name)
                await backend.call("setFontSize", float(eyebrow_font_size_pt), eyebrow_name)
                await backend.call("setTextColor", eyebrow_color, eyebrow_name)
            cur_y += 5

        # Title
        title_h = max(8.0, title_font_size_pt * 0.6)
        tr = await backend.call("createText", x_mm + padding_x_mm, cur_y, text_w, title_h)
        if tr.ok:
            title_name = tr.value
            await backend.call("setText", title, title_name)
            await backend.call("setFontSize", float(title_font_size_pt), title_name)
            await backend.call("setTextColor", title_color, title_name)
        cur_y += title_h

        # Subtitle
        if subtitle:
            sr = await backend.call("createText", x_mm + padding_x_mm, cur_y, text_w, 5)
            if sr.ok:
                subtitle_name = sr.value
                await backend.call("setText", subtitle, subtitle_name)
                await backend.call("setFontSize", float(subtitle_font_size_pt), subtitle_name)
                await backend.call("setTextColor", subtitle_color, subtitle_name)

        # Right-edge text (vertically centered in the band)
        if right_text:
            ry = y_mm + (height_mm - 5) / 2
            rr = await backend.call(
                "createText",
                x_mm + width_mm - padding_x_mm - right_w,
                ry,
                right_w,
                5,
            )
            if rr.ok:
                right_name = rr.value
                await backend.call("setText", right_text, right_name)
                await backend.call("setFontSize", float(right_font_size_pt), right_name)
                await backend.call("setTextColor", right_color, right_name)
                await backend.call("setTextAlignment", 2, right_name)  # right-aligned

        return {
            "ok": True,
            "band": band,
            "eyebrow": eyebrow_name,
            "title": title_name,
            "subtitle": subtitle_name,
            "right_text": right_name,
            "bottom_y_mm": y_mm + height_mm,
            "error": None,
        }

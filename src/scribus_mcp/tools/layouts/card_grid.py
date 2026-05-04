"""2D grid of cards — eyebrow + title + body, with a configurable accent
stripe per card. Replaces the typical hand-roll for "use cases" / "feature
grid" / "team bio" pages.

Each cell is computed by ``compute_grid_bboxes``; the card itself is
composed inline (background rect + accent stripe + eyebrow + title + body).
"""

from __future__ import annotations

import math

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools._fit import FIT_TEXT_FRAME_HELPER
from scribus_mcp.tools.layouts._geometry import compute_grid_bboxes

_ALIGN = {"left": 0, "center": 1, "right": 2, "justify": 3, "forced": 4}
_VALID_SIDES = {"left", "top", "right", "bottom"}


async def _render_card(
    backend,
    *,
    bbox: dict,
    title: str,
    body: str,
    eyebrow: str = "",
    accent_color: str,
    accent_side: str,
    accent_thickness_mm: float,
    fill_color: str,
    fill_shade: int,
    border_color: str,
    border_shade: int,
    border_width_pt: float,
    corner_radius_pt: float,
    title_color: str,
    title_font_size_pt: float,
    eyebrow_color: str,
    eyebrow_font_size_pt: float,
    body_color: str,
    body_font_size_pt: float,
    body_alignment: str,
    body_line_spacing_pt: float,
    padding_mm: float,
    auto_height: bool = False,
) -> dict:
    """Render a single card. Returns the names of every piece."""
    title = clean_user_text(title)
    body = clean_user_text(body)
    eyebrow = clean_user_text(eyebrow)
    cx, cy = bbox["x_mm"], bbox["y_mm"]
    cw, ch = bbox["width_mm"], bbox["height_mm"]

    # Background rectangle
    bgr = await backend.call("createRect", cx, cy, cw, ch)
    if not bgr.ok:
        return {"ok": False, "error": f"background failed: {bgr.error}"}
    bg = bgr.value
    await backend.call("setFillColor", fill_color, bg)
    await backend.call("setFillShade", int(fill_shade), bg)
    await backend.call("setLineColor", border_color, bg)
    await backend.call("setLineShade", int(border_shade), bg)
    await backend.call("setLineWidth", float(border_width_pt), bg)
    if corner_radius_pt > 0:
        await backend.call("setCornerRadius", round(corner_radius_pt), bg)

    # Accent stripe on chosen edge
    stripe_name = None
    if accent_side == "left":
        sx, sy, sw, sh = cx, cy, accent_thickness_mm, ch
    elif accent_side == "right":
        sx, sy, sw, sh = cx + cw - accent_thickness_mm, cy, accent_thickness_mm, ch
    elif accent_side == "top":
        sx, sy, sw, sh = cx, cy, cw, accent_thickness_mm
    elif accent_side == "bottom":
        sx, sy, sw, sh = cx, cy + ch - accent_thickness_mm, cw, accent_thickness_mm
    else:
        sx = sy = sw = sh = 0

    if sw > 0 and sh > 0:
        sr = await backend.call("createRect", sx, sy, sw, sh)
        if sr.ok:
            stripe_name = sr.value
            await backend.call("setFillColor", accent_color, stripe_name)
            await backend.call("setLineColor", "None", stripe_name)

    # Padding on the side that hosts the stripe accounts for stripe thickness.
    pad_left = accent_thickness_mm + padding_mm if accent_side == "left" else padding_mm
    pad_right = accent_thickness_mm + padding_mm if accent_side == "right" else padding_mm
    pad_top = accent_thickness_mm + padding_mm if accent_side == "top" else padding_mm
    pad_bottom = accent_thickness_mm + padding_mm if accent_side == "bottom" else padding_mm

    text_x = cx + pad_left
    text_w = cw - pad_left - pad_right
    cur_y = cy + pad_top

    # Eyebrow (optional)
    eyebrow_name = None
    if eyebrow:
        er = await backend.call("createText", text_x, cur_y, text_w, 4)
        if er.ok:
            eyebrow_name = er.value
            await backend.call("setText", eyebrow.upper(), eyebrow_name)
            await backend.call("setFontSize", float(eyebrow_font_size_pt), eyebrow_name)
            await backend.call("setTextColor", eyebrow_color, eyebrow_name)
        cur_y += 5

    # Title
    title_h = max(8.0, title_font_size_pt * 0.6)
    tr = await backend.call("createText", text_x, cur_y, text_w, title_h)
    title_name = None
    if tr.ok:
        title_name = tr.value
        await backend.call("setText", title, title_name)
        await backend.call("setFontSize", float(title_font_size_pt), title_name)
        await backend.call("setTextColor", title_color, title_name)
    cur_y += title_h + 1.5

    # Body fills the remaining space
    body_h = (cy + ch - pad_bottom) - cur_y
    body_h = max(6.0, body_h)
    br = await backend.call("createText", text_x, cur_y, text_w, body_h)
    body_name = None
    if br.ok:
        body_name = br.value
        await backend.call("setText", body, body_name)
        await backend.call("setFontSize", float(body_font_size_pt), body_name)
        await backend.call("setTextColor", body_color, body_name)
        await backend.call("setTextAlignment", _ALIGN[body_alignment], body_name)
        await backend.call("setLineSpacing", float(body_line_spacing_pt), body_name)

    final_h = ch
    if auto_height and body_name:
        # Measure body height after layout, then resize bg + stripe so
        # the card fits its content snugly. Title block height stays
        # fixed; body grows or shrinks to actual rendered text.
        title_block_h = cur_y - cy  # everything above the body
        fit_script = f"""
import scribus as _s
{FIT_TEXT_FRAME_HELPER}

_fit_h = _fit_text_frame({body_name!r}, {text_w}, {body_h})
_card_h = {title_block_h} + _fit_h + {pad_bottom}
_s.sizeObject({cw}, _card_h, {bg!r})
"""
        if stripe_name and accent_side in ("left", "right"):
            fit_script += (
                f"_s.sizeObject({accent_thickness_mm}, _card_h, {stripe_name!r})\n"
            )
        elif stripe_name and accent_side == "bottom":
            # Bottom stripe needs to follow the card's new bottom edge.
            fit_script += (
                f"_s.moveObjectAbs({cx}, {cy} + _card_h - {accent_thickness_mm}, "
                f"{stripe_name!r})\n"
            )
        fit_script += "_value = _card_h\n"
        fit_res = await backend.script(fit_script, result_expr="_value")
        if fit_res.ok and isinstance(fit_res.value, (int, float)):
            final_h = float(fit_res.value)

    return {
        "ok": True,
        "background": bg,
        "stripe": stripe_name,
        "eyebrow": eyebrow_name,
        "title": title_name,
        "body": body_name,
        "accent_side": accent_side,
        "height_mm": final_h,
        "error": None,
    }


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_card_grid(
        items: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        columns: int = 2,
        column_gap_mm: float = 4.0,
        row_gap_mm: float = 4.0,
        accent_color: str = "Black",
        accent_side: str = "left",
        accent_thickness_mm: float = 2.0,
        fill_color: str = "Black",
        fill_shade: int = 8,
        border_color: str = "Black",
        border_shade: int = 25,
        border_width_pt: float = 0.5,
        corner_radius_pt: float = 4,
        title_color: str = "Black",
        title_font_size_pt: float = 14.0,
        eyebrow_color: str = "Black",
        eyebrow_font_size_pt: float = 7.0,
        body_color: str = "Black",
        body_font_size_pt: float = 9.0,
        body_alignment: str = "justify",
        body_line_spacing_pt: float = 12.0,
        padding_mm: float = 6.0,
        auto_height: bool = False,
        mode: Mode = "auto",
    ) -> dict:
        """Render a 2D grid of cards inside (x, y, width, height).

        ``items`` is a list of dicts. Each dict requires:
            ``title``: short headline
            ``body`` : longer description
        Optional per-item overrides:
            ``eyebrow``      — small caps label above the title
            ``accent_color`` — overrides the row-level default
            ``accent_side``  — overrides the row-level default ∈ {left,top,right,bottom}

        ``columns`` is the grid width; rows = ceil(len(items)/columns). Each
        cell's bbox comes from ``compute_grid_bboxes`` so the grid never
        overflows. Set ``accent_thickness_mm=0`` to omit accent stripes.

        ``auto_height=True`` measures each card's body text after layout
        and shrinks the card chrome to fit. Within a row, every card
        adopts the row's tallest fitted height so the cards line up.
        Subsequent rows are repacked accordingly. The result's
        ``grid_height_mm`` field carries the total (possibly shrunk)
        grid height — chain it via ``PageCursor.jump_to``.

        Returns the names of every piece for each card so callers can re-style.
        """
        if not items:
            return {"ok": False, "error": "items must not be empty"}
        for i, it in enumerate(items):
            if "title" not in it or "body" not in it:
                return {"ok": False, "error": f"item {i} needs 'title' and 'body'"}
        if columns < 1:
            return {"ok": False, "error": "columns must be >= 1"}
        if accent_side not in _VALID_SIDES:
            return {"ok": False, "error": f"accent_side must be one of {sorted(_VALID_SIDES)}"}
        if body_alignment not in _ALIGN:
            return {"ok": False, "error": f"body_alignment must be one of {sorted(_ALIGN)}"}

        n = len(items)
        rows = math.ceil(n / columns)
        bboxes = compute_grid_bboxes(
            x_mm,
            y_mm,
            width_mm,
            height_mm,
            rows,
            columns,
            column_gap_mm=column_gap_mm,
            row_gap_mm=row_gap_mm,
        )
        if not bboxes:
            return {
                "ok": False,
                "error": "could not compute grid bboxes (bbox too small for rows×cols + gaps)",
            }

        backend = await get_backend(ctx, mode)
        cards: list[dict] = []
        for i, it in enumerate(items):
            it_side = it.get("accent_side", accent_side)
            if it_side not in _VALID_SIDES:
                return {
                    "ok": False,
                    "error": f"item {i}: accent_side must be one of {sorted(_VALID_SIDES)}",
                    "cards": cards,
                }
            r = await _render_card(
                backend,
                bbox=bboxes[i],
                title=str(it["title"]),
                body=str(it["body"]),
                eyebrow=str(it.get("eyebrow", "")),
                accent_color=str(it.get("accent_color", accent_color)),
                accent_side=it_side,
                accent_thickness_mm=float(accent_thickness_mm),
                fill_color=str(it.get("fill_color", fill_color)),
                fill_shade=int(it.get("fill_shade", fill_shade)),
                border_color=str(it.get("border_color", border_color)),
                border_shade=int(it.get("border_shade", border_shade)),
                border_width_pt=float(border_width_pt),
                corner_radius_pt=float(corner_radius_pt),
                title_color=str(it.get("title_color", title_color)),
                title_font_size_pt=float(title_font_size_pt),
                eyebrow_color=str(it.get("eyebrow_color", eyebrow_color)),
                eyebrow_font_size_pt=float(eyebrow_font_size_pt),
                body_color=str(body_color),
                body_font_size_pt=float(body_font_size_pt),
                body_alignment=str(body_alignment),
                body_line_spacing_pt=float(body_line_spacing_pt),
                padding_mm=float(padding_mm),
                auto_height=auto_height,
            )
            if not r.get("ok"):
                return {"ok": False, "error": f"card {i} failed: {r.get('error')}", "cards": cards}
            # Stash original bbox so the per-row uniform pass + the
            # row-repack can see card geometry.
            r["_bbox"] = dict(bboxes[i])
            cards.append(r)

        grid_height_mm = float(height_mm)
        if auto_height and cards:
            # Per-row uniformity + repack subsequent rows up to remove the
            # gap left by shrunk cards above. We do this in two passes:
            # 1. group by row; for each row, find max fitted height; resize
            #    every card in that row to match.
            # 2. accumulate row tops top-down; shift cards in row r to start
            #    at the previous row's bottom + ``row_gap_mm``.
            rows_of_cards: list[list[int]] = [
                list(range(r * columns, min((r + 1) * columns, n)))
                for r in range(rows)
            ]
            row_max_h: list[float] = []
            for row_idxs in rows_of_cards:
                hs = [
                    float(cards[i].get("height_mm") or cards[i]["_bbox"]["height_mm"])
                    for i in row_idxs
                ]
                row_max_h.append(max(hs) if hs else 0.0)

            cur_top = float(y_mm)
            resize_calls: list[str] = []
            for row_idx, row_idxs in enumerate(rows_of_cards):
                target_h = row_max_h[row_idx]
                for i in row_idxs:
                    card = cards[i]
                    bbox = card["_bbox"]
                    bg = card.get("background")
                    stripe = card.get("stripe")
                    side = card.get("accent_side", accent_side)
                    new_x = bbox["x_mm"]
                    new_y = cur_top
                    cw = bbox["width_mm"]
                    if bg:
                        resize_calls.append(
                            f"_s.sizeObject({cw}, {target_h}, {bg!r})"
                        )
                        resize_calls.append(
                            f"_s.moveObjectAbs({new_x}, {new_y}, {bg!r})"
                        )
                    if stripe:
                        if side in ("left", "right"):
                            sx = (
                                new_x
                                if side == "left"
                                else new_x + cw - accent_thickness_mm
                            )
                            resize_calls.append(
                                f"_s.sizeObject({accent_thickness_mm}, {target_h}, "
                                f"{stripe!r})"
                            )
                            resize_calls.append(
                                f"_s.moveObjectAbs({sx}, {new_y}, {stripe!r})"
                            )
                        elif side == "top":
                            resize_calls.append(
                                f"_s.moveObjectAbs({new_x}, {new_y}, {stripe!r})"
                            )
                        elif side == "bottom":
                            resize_calls.append(
                                f"_s.moveObjectAbs({new_x}, "
                                f"{new_y + target_h - accent_thickness_mm}, "
                                f"{stripe!r})"
                            )
                    # Shift the (already-fitted) text frames vertically by
                    # the same delta as the bg, so they stay aligned.
                    # ``moveObject`` is relative; we don't need each frame's
                    # original y, just the row-level delta.
                    dy = new_y - bbox["y_mm"]
                    if dy:
                        for key in ("eyebrow", "title", "body"):
                            nm = card.get(key)
                            if nm:
                                resize_calls.append(
                                    f"_s.moveObject(0, {dy}, {nm!r})"
                                )
                    card["_bbox"]["y_mm"] = new_y  # update for chained reads
                    card["height_mm"] = target_h
                cur_top += target_h + row_gap_mm

            if resize_calls:
                pack_script = "import scribus as _s\n" + "\n".join(resize_calls)
                pack_res = await backend.script(pack_script, result_expr="None")
                if not pack_res.ok:
                    return {
                        "ok": False,
                        "error": f"row uniformity pack failed: {pack_res.error}",
                        "cards": cards,
                    }
            grid_height_mm = cur_top - row_gap_mm - float(y_mm)

        # Strip internal-only ``_bbox`` field before returning.
        for c in cards:
            c.pop("_bbox", None)

        return {
            "ok": True,
            "cards": cards,
            "rows": rows,
            "columns": columns,
            "count": n,
            "grid_height_mm": grid_height_mm,
            "error": None,
        }

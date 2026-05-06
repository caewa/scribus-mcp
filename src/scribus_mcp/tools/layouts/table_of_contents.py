"""Manual table of contents with leader dots and page numbers.

Scribus's Scripter API does not expose auto-generated TOC entries (those
are a separate Scribus feature configured in the GUI). This is a
manually-composed TOC: pass it the entries + page numbers and it lays out
``Title …………………… 12``-style lines.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, clean_user_text, get_backend
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_table_of_contents(
        entries: list[dict],
        x_mm: float,
        y_mm: float,
        width_mm: float,
        line_height_mm: float = 6.0,
        title: str = "",
        title_color: str = "ink",
        title_font_size_pt: float = 14.0,
        title_height_mm: float = 8.0,
        title_gap_mm: float = 4.0,
        entry_color: str = "ink",
        entry_font_size_pt: float = 10.0,
        page_number_color: str = "muted",
        leader_char: str = ".",
        leader_color: str = "muted",
        leader_shade: int | None = None,
        leader_font_size_pt: float = 10.0,
        indent_per_level_mm: float = 6.0,
        page_column_width_mm: float = 12.0,
        mode: Mode = "auto",
    ) -> dict:
        """Render a manual table of contents.

        ``entries`` is a list of dicts:
            {"title": str, "page": int, "level": int (optional, default 0)}

        ``level=0`` is top-level; higher levels are indented by
        ``indent_per_level_mm`` per step. Each line has the title on the
        left, a column of leader characters (default dots), and the page
        number flush-right.
        """
        if not entries:
            return {"ok": False, "error": "entries must not be empty"}
        for i, e in enumerate(entries):
            if "title" not in e or "page" not in e:
                return {"ok": False, "error": f"entry {i} needs 'title' and 'page'"}

        backend = await get_backend(ctx, mode)
        title_color, _ = await resolve_color(backend, title_color)
        entry_color, _ = await resolve_color(backend, entry_color)
        page_number_color, _ = await resolve_color(backend, page_number_color)
        leader_color, leader_shade = await resolve_color(
            backend, leader_color, fallback_shade=35, current_shade=leader_shade,
        )
        title = clean_user_text(title)
        cur_y = y_mm
        title_name: str | None = None
        entry_names: list[dict] = []

        # Optional title
        if title:
            tr = await backend.call("createText", x_mm, cur_y, width_mm, title_height_mm)
            if tr.ok:
                title_name = tr.value
                await backend.call("setText", title, title_name)
                await backend.call("setFontSize", float(title_font_size_pt), title_name)
                await backend.call("setTextColor", title_color, title_name)
            cur_y += title_height_mm + title_gap_mm

        # Each entry: 3 frames — title (left), leader dots (middle, fills),
        # page number (right, fixed width).
        page_col_x = x_mm + width_mm - page_column_width_mm

        for e in entries:
            level = int(e.get("level", 0))
            indent = max(0, level) * indent_per_level_mm
            title_x = x_mm + indent
            title_w = max(20.0, page_col_x - title_x - 4)
            leader_x = title_x + title_w
            leader_w = page_col_x - leader_x

            # Title
            tr = await backend.call("createText", title_x, cur_y, title_w, line_height_mm)
            tn = None
            if tr.ok:
                tn = tr.value
                await backend.call("setText", clean_user_text(str(e["title"])), tn)
                await backend.call("setFontSize", float(entry_font_size_pt), tn)
                await backend.call("setTextColor", entry_color, tn)

            # Leader (dots filling the gap)
            ldn = None
            if leader_w > 2:
                lr = await backend.call("createText", leader_x, cur_y, leader_w, line_height_mm)
                if lr.ok:
                    ldn = lr.value
                    # Fill with enough leader chars to span the column. At ~1.5pt per dot,
                    # leader_w (mm) * 2 is a generous overestimate Scribus will clip.
                    n_dots = max(8, int(leader_w * 2.5))
                    await backend.call("setText", leader_char * n_dots, ldn)
                    await backend.call("setFontSize", float(leader_font_size_pt), ldn)
                    await backend.call("setTextColor", leader_color, ldn)
                    if leader_shade != 100:
                        await backend.call("setTextShade", int(leader_shade), ldn)

            # Page number (right-aligned)
            pr = await backend.call(
                "createText",
                page_col_x,
                cur_y,
                page_column_width_mm,
                line_height_mm,
            )
            pn = None
            if pr.ok:
                pn = pr.value
                await backend.call("setText", str(int(e["page"])), pn)
                await backend.call("setFontSize", float(entry_font_size_pt), pn)
                await backend.call("setTextColor", page_number_color, pn)
                await backend.call("setTextAlignment", 2, pn)  # right-aligned

            entry_names.append({"title": tn, "leader": ldn, "page_number": pn, "level": level})
            cur_y += line_height_mm

        group_name = await group_created_objects(
            backend, [title_name] + list(entry_names or [])
        )
        return {
            "ok": True,
            "title": title_name,
            "entries": entry_names,
            "group": group_name,
            "bottom_y_mm": cur_y,
            "error": None,
        }

# scribus-mcp cookbook

End-to-end recipes for the most common things people build with this MCP. Each recipe assumes the [interactive bridge](../README.md#enable-the-interactive-backend) is running (or `mode="headless"` if you're driving a one-shot job).

For an LLM driving the MCP from a Claude/Anthropic session, the equivalent rule sheet is exposed as the `best_practices` MCP prompt — pull it at session start.

---

## Table of contents

1. [Common setup](#1-common-setup) — A4 doc, brand palette, page chrome
2. [Dashboard one-pager](#2-dashboard-one-pager) — KPIs, charts, callout, timeline
3. [Multi-page manual from Markdown](#3-multi-page-manual-from-markdown)
4. [Comparison report (multi-dataset)](#4-comparison-report-multi-dataset)
5. [Code-walkthrough document](#5-code-walkthrough-document)
6. [PDF form / interactive document](#6-pdf-form--interactive-document)
7. [Custom-font document](#7-custom-font-document)
8. [Recurring patterns reference](#8-recurring-patterns-reference)

---

## 1. Common setup

Every recipe starts the same way: a fresh A4 portrait, a small brand palette, a `PageCursor` for vertical flow, and a `page_chrome()` helper for repeated header/footer.

```python
import asyncio, json
from scribus_mcp.server import build_server
from scribus_mcp.layout import PageCursor


def unwrap(out):
    if isinstance(out, list) and out:
        txt = getattr(out[0], "text", None) or str(out[0])
        try: return json.loads(txt)
        except json.JSONDecodeError: return {"raw": txt}
    if isinstance(out, tuple) and len(out) == 2:
        c, s = out
        return s if s else unwrap(c)
    return out


async def main():
    mcp = build_server()
    async def t(_tool, **kw):
        kw.setdefault("mode", "interactive")
        return unwrap(await mcp.call_tool(_tool, kw))

    await t("close_document")
    await t(
        "create_document",
        width_mm=210, height_mm=297,
        margin_top_mm=12, margin_left_mm=12,
        margin_right_mm=12, margin_bottom_mm=12,
    )

    # Brand palette — define before any tool references these names.
    for n, c, m, y, k in (
        ("Brand Deep",  85, 55, 0, 10),
        ("Brand Mid",   65, 30, 0, 0),
        ("Brand Light", 35, 8,  0, 0),
        ("Accent",       0, 70, 85, 0),
        ("Ink",          0,  0,  0, 85),
    ):
        await t("define_color_cmyk", name=n, cyan=c, magenta=m, yellow=y, key=k)

    pc = PageCursor(x_mm=12, y_mm=22, width_mm=186, default_gap_mm=4)
    await build_my_page(t, pc)

    await t("save_document_as", path="out.sla")
    await t("export_pdf", path="out.pdf", pages="all", resolution=200)


asyncio.run(main())
```

A `page_chrome` helper for documents with repeated headers:

```python
async def page_chrome(t, page_num: int, total: int, accent: str, title: str):
    """Header band + footer per page. Use create_master_page + apply_master_page
    if you'd rather have proper masters; this is the inline approach."""
    await t(
        "create_hero_band",
        title=title,
        eyebrow=f"PAGE {page_num} OF {total}",
        right_text="my-org · v1.0",
        x_mm=0, y_mm=0, width_mm=210, height_mm=18,
        fill_color=accent,
    )
    foot = await t("create_text_frame", x_mm=12, y_mm=287, width_mm=186, height_mm=5)
    await t("set_text", name=foot["name"], text=f"page {page_num} / {total}")
    await t("set_font_size", name=foot["name"], size_pt=7)
    await t("set_text_color", name=foot["name"], color="Ink")
    await t("set_text_alignment", name=foot["name"], alignment="center")
```

---

## 2. Dashboard one-pager

Header → KPI row → bar/pie split → radar + callout split → timeline → comparison table. This is the [showcase demo](../scripts/demo-showcase.py) shape.

```python
async def build_dashboard(t, pc):
    # 1. KPI row (4 tiles, auto-distributed)
    await t(
        "create_kpi_row",
        items=[
            {"value": "125", "label": "MCP tools",       "delta": "across 17 modules", "fill_color": "Brand Mid"},
            {"value": "136", "label": "tests passing",   "delta": "Phase 1 + 2 green", "fill_color": "Brand Deep"},
            {"value": "17",  "label": "tool categories", "delta": "patterns, layouts…", "fill_color": "Accent"},
            {"value": "22",  "label": "git commits",     "delta": "still local",        "fill_color": "Brand Mid"},
        ],
        **pc.band(height_mm=38),  # cursor advances 38 + default_gap
        gap_mm=3, fill_shade=12, value_color="Ink", value_font_size_pt=22,
    )

    # 2. Bar + pie sharing a 45 mm band
    bar, pie = pc.split(widths_mm=[85, 101], height_mm=45)
    await t(
        "create_bar_chart",
        labels=["Q1", "Q2", "Q3", "Q4"], values=[120, 180, 95, 245],
        x_mm=bar["x_mm"], y_mm=bar["y_mm"],
        width_mm=bar["width_mm"], height_mm=bar["height_mm"],
        bar_color="Brand Mid", show_values=True,
    )
    await t(
        "create_pie_chart",
        labels=["Primitives", "Patterns", "Layouts", "Forms"],
        values=[80, 11, 11, 13],
        center_x_mm=pie["center_x"] - 8, center_y_mm=pie["center_y"], radius_mm=18,
        colors=["Brand Deep", "Brand Mid", "Accent", "Brand Light"],
        outer_ring_color="White", legend_label_width_mm=28,
    )

    # 3. Radar + callout split
    radar, cb = pc.split(widths_mm=[80, 106], height_mm=56)
    await t(
        "create_radar_chart",
        axes=["Coverage", "Speed", "Reliability", "DX", "Docs", "UX"],
        values=[0.95, 0.85, 0.9, 0.8, 0.7, 0.75],
        center_x_mm=radar["center_x"], center_y_mm=radar["center_y"], radius_mm=22,
        data_fill_color="Brand Deep",
    )
    await t(
        "create_callout_box",
        title="What this dashboard shows",
        body="Every element is one MCP call. KPIs, charts, callouts, timeline, table — all composed live.",
        x_mm=cb["x_mm"], y_mm=cb["y_mm"],
        width_mm=cb["width_mm"], height_mm=cb["height_mm"],
        fill_color="Brand Light", fill_shade=18,
        border_color="Brand Mid", title_color="Brand Deep",
    )

    # 4. Timeline (use top_y_mm so labels stay inside the slot)
    tl = pc.band(height_mm=22)
    await t(
        "create_timeline",
        items=[
            {"position": 0.0,  "label": "Init",          "date": "May 1"},
            {"position": 0.25, "label": "Tests green",   "date": "May 1"},
            {"position": 0.5,  "label": "Patterns",      "date": "May 2"},
            {"position": 0.75, "label": "Forms",         "date": "May 2"},
            {"position": 1.0,  "label": "Multi-dataset", "date": "May 3"},
        ],
        x_mm=tl["x_mm"] + 6, top_y_mm=tl["y_mm"], width_mm=tl["width_mm"] - 12,
        axis_color="Brand Deep",
    )

    # 5. Comparison table
    tbl = pc.band(height_mm=32)
    await t(
        "create_comparison_table",
        headers=["Backend", "Latency", "Persistent", "Best for"],
        rows=[
            ["Headless",      "~3 s/call",  "no",  "CI batch"],
            ["Bridge (Qt)",   "~50 ms/call","yes", "Live editing"],
            ["Bridge (no Qt)","~50 ms/call","yes", "Headless persistent"],
        ],
        x_mm=tbl["x_mm"] + 6, y_mm=tbl["y_mm"], width_mm=tbl["width_mm"] - 12,
        column_widths=[40, 32, 32, 80],
        zebra=True, zebra_fill_color="Brand Light",
    )
```

**Key rules** illustrated:

- `PageCursor.band` / `split` for vertical flow.
- `bar_chart.height_mm` is **inclusive** of label strips — pass the slot's full height.
- For pie/radar: splat the slot's `center_x` / `center_y` into `center_x_mm` / `center_y_mm`.
- For pie in narrow slots: shrink `legend_label_width_mm` and shift the pie left.
- For timeline: use `top_y_mm` so labels stay inside the band; `axis_y_mm` if you want explicit axis placement.

---

## 3. Multi-page manual from Markdown

For a Markdown manual, use `import_markdown` rather than walking the tree by hand. It handles headings (h1–h6), paragraphs, lists, fenced code, images, plus inline `**bold**` / `*italic*` / `` `code` `` (auto-discovers font variants).

```python
async def build_manual(t):
    md = open("manual.md", encoding="utf-8").read()

    # Page 1 chrome
    await page_chrome(t, page_num=1, total=3, accent="Brand Deep",
                      title="User Manual")

    # Drop the markdown stack starting under the header. import_markdown
    # uses a measure-and-resize loop (textOverflows) so each block is
    # sized to its actual rendered text — no big gaps between paragraphs.
    r = await t(
        "import_markdown",
        markdown_text=md,
        x_mm=12, y_mm=24, width_mm=186,
    )
    # r["value"]["final_y_mm"] tells you where the stack ended; if that's
    # past the page, add a page and continue.

    if (r.get("value") or {}).get("final_y_mm", 0) > 280:
        await t("add_page")
        await t("goto_page", page_number=2)
        # ... keep going on page 2

    # Verify before exporting
    await t("preflight_check")
    await t("save_document_as", path="manual.sla")
    await t("export_pdf", path="manual.pdf", pages="all", resolution=200)
```

For long content, link the resulting text frames with `link_text_frames(from_frame, to_frame)` so the markdown body reflows across pages.

There's also an MCP prompt — `manual_from_markdown` — that returns a step-by-step plan for an LLM.

---

## 4. Comparison report (multi-dataset)

For "Plan vs Actual", "2024 vs 2025 vs 2026", etc. — use the `datasets=[…]` form on `create_radar_chart` and `create_bar_chart`. Each entry is its own polygon / bar group, color-coded, with an auto-rendered legend below.

```python
# Multi-dataset radar — overlapping polygons with partial transparency
await t(
    "create_radar_chart",
    axes=["Coverage", "Speed", "Reliability", "DX", "Docs", "UX"],
    datasets=[
        {"label": "Plan",   "values": [0.7, 0.6, 0.8, 0.5, 0.4, 0.5],
         "fill_color": "Brand Mid",  "line_color": "Brand Mid",  "fill_alpha": 0.4},
        {"label": "Actual", "values": [0.95, 0.85, 0.9, 0.8, 0.7, 0.75],
         "fill_color": "Accent",     "line_color": "Accent",     "fill_alpha": 0.4},
    ],
    center_x_mm=70, center_y_mm=180, radius_mm=30,
)

# Grouped bar chart — N adjacent bars per category
await t(
    "create_bar_chart",
    labels=["Q1", "Q2", "Q3", "Q4"],
    datasets=[
        {"label": "2024", "values": [10, 12, 8,  14], "fill_color": "Brand Deep", "fill_shade": 50},
        {"label": "2025", "values": [12, 18, 9,  17], "fill_color": "Brand Mid",  "fill_shade": 80},
        {"label": "2026", "values": [15, 22, 14, 25], "fill_color": "Accent",     "fill_shade": 80},
    ],
    x_mm=20, y_mm=30, width_mm=170, height_mm=70,
)
```

Both charts auto-render a legend below by default (`legend_position="below"`); pass `"none"` to suppress.

---

## 5. Code-walkthrough document

For documenting an API or showing examples, use `create_code_sample` — Pygments tokenizes the source, the tool defines per-token colors in the document, picks a monospace font from the installed set, and applies colors per range via `selectText` + `setTextColor`.

```python
sample_py = """\
from scribus_mcp import build_server
import asyncio

async def main():
    mcp = build_server()
    out = await mcp.call_tool(
        'create_code_sample',
        {'code': source, 'language': 'python'})
    return out
"""

await t(
    "create_code_sample",
    code=sample_py,
    language="python",
    x_mm=12, y_mm=24, width_mm=186, height_mm=64,
    title="example.py",
    title_color="White", title_fill_color="Brand Deep",
    font_size_pt=8.5, show_line_numbers=True,
    style="default",  # or "monokai", "friendly", "github-dark", …
)
```

The tool returns the names of the title bar, the code frame, and the background — so callers can re-style after the fact.

---

## 6. PDF form / interactive document

Form fields and annotations go through the [`forms` package](../src/scribus_mcp/tools/forms/). Six field types + four annotation types + JS action set/get for all 10 events.

```python
# A name field
name_field = await t(
    "create_pdf_text_field",
    x_mm=20, y_mm=30, width_mm=80, height_mm=8,
    name="full_name",
)

# A consent checkbox
await t("create_pdf_checkbox", x_mm=20, y_mm=45, width_mm=4, height_mm=4, name="consent")

# A submit button that runs JS
await t(
    "create_pdf_push_button",
    x_mm=20, y_mm=60, width_mm=30, height_mm=8,
    label="Submit", action_js="this.print();",
)

# A URI annotation that auto-creates its frame
await t(
    "create_uri_annotation",
    uri="https://github.com/caewa/scribus-mcp",
    frame_x_mm=20, frame_y_mm=80, frame_width_mm=60, frame_height_mm=6,
    link_text="View source on GitHub",
)

# A page-link annotation — target_x_mm/target_y_mm are coords on the
# DESTINATION page; frame_x_mm etc. are where the clickable rect sits
# on the CURRENT page.
await t(
    "create_link_annotation",
    target_page=2, target_x_mm=20, target_y_mm=20,
    frame_x_mm=20, frame_y_mm=90, frame_width_mm=40, frame_height_mm=6,
    link_text="Jump to page 2",
)

# A reviewer sticky-note
await t(
    "create_text_annotation",
    text="Reviewer: please double-check the address",
    x_mm=180, y_mm=30, icon="comment",
)
```

For per-event JS handlers (calculate, validate, format, focus, blur, …), use `set_js_action(name, event, script)`.

---

## 7. Custom-font document

Scribus discovers fonts at startup. To use a font Scribus doesn't yet know about:

```python
# Stage the font for the next launch
await t(
    "install_custom_font",
    font_path="/path/to/MyBrandFont-Regular.ttf",
    register_with_scribus=True,
)
# → copies font into <runtime_dir>/fonts/, patches Scribus's per-user
#   prefs to add that dir to Additional Font Paths. Returns
#   restart_required=True.

# Restart Scribus, then verify
r = await t("font_is_available", font="MyBrandFont")
assert r["available"]

# Use it
await t(
    "create_text_frame",
    x_mm=20, y_mm=20, width_mm=170, height_mm=30,
    name="title",
)
await t("set_text", name="title", text="Brand title")
await t("set_font", name="title", font="MyBrandFont Regular")
```

For headless CI: set `SCRIBUS_MCP_EXTRA_FONT_PATHS=/path/to/fonts` and every spawned Scribus gets a temp prefs dir with that path registered — no user prefs touched.

---

## 8. Recurring patterns reference

| Shape you want | Tool to reach for |
|---|---|
| 4 stat tiles in a row | `create_kpi_row` |
| Vertical numbered steps (Getting Started) | `create_numbered_steps` |
| 2×N grid of feature cards | `create_card_grid` |
| Two-column body text | `create_two_column_text` |
| Image + caption (figure) | `create_image_caption` |
| Sidebar + main column | `create_sidebar_layout` |
| Big intro band w/ title + subtitle | `create_hero_band` |
| Section header (eyebrow + title + rule) | `create_section_header` |
| Bordered tip / warning / pull-quote | `create_callout_box` |
| Highlighted code block | `create_code_sample` |
| Numbered status badge | `create_numbered_badge` |
| Filled circle with label | `create_dot_label` |
| Comparative table | `create_comparison_table` |
| Horizontal milestone timeline | `create_timeline` |
| Bar / pie / radar chart | `create_bar_chart` / `create_pie_chart` / `create_radar_chart` |
| QR code + caption | `create_qr_code_block` |
| Markdown → page | `import_markdown` |

| Helper you want | Where to find it |
|---|---|
| Vertical-flow cursor | `from scribus_mcp.layout import PageCursor` |
| List installed fonts | `list_fonts` / `list_monospace_fonts` |
| Define brand colors | `define_color_cmyk` / `define_color_rgb` |
| Inspect the open doc | resource `scribus://document/info` |
| Find missing fonts/images | resource `scribus://document/missing-resources` |
| Render a page preview inline | `render_page_to_image` |
| Pre-export validation | `preflight_check` |

| Behaviour you wish you knew | Where it's documented |
|---|---|
| Which Scripter functions are wrapped? | [doc/SUPPORT.md](SUPPORT.md) |
| Why is the bridge two-piece? | [doc/threading-and-scribus.md](threading-and-scribus.md) |
| What rules should an LLM follow? | MCP prompt `best_practices` |

---

## See also

- The two demo scripts dogfood every recipe here:
  - [scripts/demo-showcase.py](../scripts/demo-showcase.py) — 2 pages, every primitive + pattern + layout
  - [scripts/demo-explainer.py](../scripts/demo-explainer.py) — 5 pages, full document walkthrough
- Run them against a live bridge to see what the output looks like; the committed `demo-showcase.{sla,pdf}` and `explainer.{sla,pdf}` are the visual reference. PNG page previews are generated locally on demand (`render_page_to_image`, or the demos' "render previews" step) and aren't committed.

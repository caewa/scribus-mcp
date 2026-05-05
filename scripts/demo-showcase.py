"""All-features showcase for scribus-mcp.

Run against a live interactive bridge (or change ``MODE = "headless"``
below). Generates a 4-page A4 demo .sla + .pdf that exercises every
category of tool the MCP exposes.

  Page 1 — Dashboard: KPI tiles, bar chart, pie chart, radar chart,
                       callout box, timeline, comparison table
  Page 2 — Showcase: shape primitives, gradients, markdown import,
                      QR code, find_and_replace, syntax-highlighted code sample
  Page 3 — Strip patterns I: dark_kpi_band + axes_strip
  Page 4 — Strip patterns II: highlight_card_row + pillar_strip

Run from the repo root with::

    uv run python scripts/demo-showcase.py

Output directory defaults to ``~/scribus-mcp-demo/`` and is created on
first run; override via ``SCRIBUS_MCP_DEMO_DIR=/some/path``. Files
written: ``demo-showcase.sla``, ``demo-showcase.pdf``,
``showcase-p{1..4}.png``.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from scribus_mcp.layout import PageCursor
from scribus_mcp.server import build_server
from scribus_mcp.testing import unwrap

OUT_DIR = Path(
    os.environ.get("SCRIBUS_MCP_DEMO_DIR")
    or Path.home() / "scribus-mcp-demo"
).expanduser()
OUT_DIR.mkdir(parents=True, exist_ok=True)
SLA = str(OUT_DIR / "demo-showcase.sla")
PDF = str(OUT_DIR / "demo-showcase.pdf")
MODE = "interactive"


LOREM_SHORT = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do "
    "eiusmod tempor incididunt ut labore et dolore magna aliqua."
)

MARKDOWN = """\
# Markdown imported

A short paragraph from a markdown source. Includes regular text and **emphasis-marked**
content, plus a list:

- imported in one tool call
- styled by the markdown parser
- replaces dozens of primitive calls
"""
# Note: we used to include a fenced code block here, but the
# create_code_sample section below is the proper showcase for code blocks
# (Pygments-tokenized vs. monospace plain text). Removed to keep the
# markdown stack short enough to fit its allotted band.


async def main() -> None:
    mcp = build_server()

    async def t(tool_name, **kwargs):
        kwargs.setdefault("mode", MODE)
        return unwrap(await mcp.call_tool(tool_name, kwargs))

    print("=== Setup ===")

    # Close any open doc so we start fresh.
    await t("close_document")

    # New A4 doc.
    r = await t(
        "create_document",
        width_mm=210,
        height_mm=297,
        margin_top_mm=12,
        margin_left_mm=12,
        margin_right_mm=12,
        margin_bottom_mm=12,
    )
    assert r.get("ok"), r
    print(f"  document: ok={r.get('ok')}")

    # Brand palette.
    palette = [
        ("Brand Deep", 85, 55, 0, 10),
        ("Brand Mid", 65, 30, 0, 0),
        ("Brand Light", 35, 8, 0, 0),
        ("Accent", 0, 70, 85, 0),
        ("Warm", 0, 35, 70, 0),
        ("Ink", 0, 0, 0, 85),
        ("Subtle", 0, 0, 0, 12),
    ]
    for name, c, m, y, k in palette:
        await t("define_color_cmyk", name=name, cyan=c, magenta=m, yellow=y, key=k)
    print(f"  palette: {len(palette)} colors defined")

    # Layers
    await t("create_layer", name="Annotations")
    print("  layers: Annotations layer created")

    # ===================== PAGE 1 — Dashboard =====================
    print("\n=== Page 1: Dashboard ===")

    # Header band (full-width rectangle, sits above the cursor area)
    band = await t("create_rectangle", x_mm=0, y_mm=0, width_mm=210, height_mm=30)
    band_name = band["name"]
    await t("set_fill_color", name=band_name, color="Brand Deep")
    await t("set_line_color", name=band_name, color="None")

    # Title (inside the header band — placed manually since headers don't
    # sit in the body cursor)
    title = await t("create_text_frame", x_mm=12, y_mm=8, width_mm=140, height_mm=14)
    await t("set_text", name=title["name"], text="scribus-mcp showcase")
    await t("set_font_size", name=title["name"], size_pt=22)
    await t("set_text_color", name=title["name"], color="White")

    sub = await t("create_text_frame", x_mm=120, y_mm=12, width_mm=80, height_mm=8)
    await t("set_text", name=sub["name"], text="generated entirely via MCP — 2026-05-03")
    await t("set_font_size", name=sub["name"], size_pt=8)
    await t("set_text_color", name=sub["name"], color="Brand Light")
    await t("set_text_alignment", name=sub["name"], alignment="right")

    # Body cursor: 12 mm side margins, content starts 8 mm under header.
    # default_gap_mm=4 — auto-inserted vertical breathing room between bands.
    pc = PageCursor(x_mm=12, y_mm=38, width_mm=186, default_gap_mm=4)

    # KPI row — single layout call, cursor advances past the band + 4 mm.
    kpis = [
        {
            "value": "125",
            "label": "MCP tools",
            "delta": "across 17 modules",
            "fill_color": "Brand Mid",
        },
        {
            "value": "136",
            "label": "tests passing",
            "delta": "Phase 1 + 2 green",
            "fill_color": "Brand Deep",
        },
        {
            "value": "17",
            "label": "tool categories",
            "delta": "patterns, layouts, forms…",
            "fill_color": "Accent",
        },
        {"value": "22", "label": "git commits", "delta": "still local", "fill_color": "Warm"},
    ]
    await t(
        "create_kpi_row",
        items=kpis,
        **pc.band(height_mm=38),
        gap_mm=3,
        fill_shade=12,
        value_color="Ink",
        value_font_size_pt=22,
        label_color="Brand Deep",
        delta_color="Ink",
    )
    print(f"  KPI tiles: {len(kpis)} created")

    # Bar chart (left, ~85 mm) + Pie chart (right, ~89 mm). Bar chart's
    # height_mm is inclusive of its label strip, so the slot's full
    # height is fine.
    bar_slot, pie_slot = pc.split(widths_mm=[85, 101], height_mm=45)

    # height_mm is now inclusive of the category-label strip — the slot's
    # full height is fine, no manual budgeting needed.
    await t(
        "create_bar_chart",
        labels=["Q1", "Q2", "Q3", "Q4"],
        values=[120, 180, 95, 245],
        x_mm=bar_slot["x_mm"],
        y_mm=bar_slot["y_mm"],
        width_mm=bar_slot["width_mm"],
        height_mm=bar_slot["height_mm"],
        bar_color="Brand Mid",
        bar_shade=85,
        gridline_color="Ink",
        gridline_shade=18,
        label_color="Ink",
        show_values=True,
    )
    print("  bar chart: created")

    # Pie chart with a tighter right legend so it stays inside the
    # printable area (the slot only has ~32 mm of headroom to the right
    # of the pie). 22 mm is enough for "Primitives — 70%" at 8 pt.
    await t(
        "create_pie_chart",
        labels=["Primitives", "Patterns", "Layouts", "Forms"],
        values=[80, 11, 11, 13],
        center_x_mm=pie_slot["center_x"] - 8,  # shift pie left to free legend space
        center_y_mm=pie_slot["center_y"],
        radius_mm=18,
        colors=["Brand Deep", "Brand Mid", "Accent", "Warm"],
        outline_color="None",
        outer_ring_color="White",
        outer_ring_width_pt=0.7,
        label_color="Ink",
        legend_label_width_mm=28,
    )
    print("  pie chart: created")

    # Radar (left ~ 80 mm) + Callout (right ~ 100 mm) sharing a 56 mm band.
    radar_slot, cb_slot = pc.split(widths_mm=[80, 106], height_mm=56)

    await t(
        "create_radar_chart",
        axes=["Coverage", "Speed", "Reliability", "DX", "Docs", "UX"],
        values=[0.95, 0.85, 0.9, 0.8, 0.7, 0.75],
        center_x_mm=radar_slot["center_x"],
        center_y_mm=radar_slot["center_y"],
        radius_mm=22,
        ring_color="Ink",
        ring_shade=18,
        axis_color="Ink",
        axis_shade=30,
        data_fill_color="Brand Deep",
        data_fill_shade=22,
        data_line_color="Brand Deep",
        data_line_width_pt=1.4,
        label_color="Ink",
    )
    print("  radar chart: created")

    await t(
        "create_callout_box",
        title="What this page demonstrates",
        body=(
            "Every visible element on this page was emitted by a single MCP tool call "
            "running through the interactive bridge. Shapes, text, colors, charts and "
            "layout primitives are all composed live from Claude. Read on to page 2 for "
            "the lower-level primitive showcase."
        ),
        x_mm=cb_slot["x_mm"],
        y_mm=cb_slot["y_mm"],
        width_mm=cb_slot["width_mm"],
        height_mm=cb_slot["height_mm"],
        fill_color="Brand Light",
        fill_shade=18,
        border_color="Brand Mid",
        border_shade=60,
        title_color="Brand Deep",
        body_color="Ink",
    )
    print("  callout box: created")

    # Timeline. ``y_mm`` is the *axis* line of the timeline; labels sit
    # ~10 mm above (label_offset+label_height) and dates ~10 mm below.
    # We allocate a 22 mm band and place the axis at slot_top+10 so the
    # whole footprint stays inside the slot.
    timeline_items = [
        {"position": 0.0, "label": "Init", "date": "May 1"},
        {"position": 0.25, "label": "Tests green", "date": "May 1"},
        {"position": 0.5, "label": "Patterns", "date": "May 2"},
        {"position": 0.75, "label": "Forms", "date": "May 2"},
        {"position": 1.0, "label": "Multi-dataset", "date": "May 3"},
    ]
    tl_slot = pc.band(height_mm=22)
    await t(
        "create_timeline",
        items=timeline_items,
        x_mm=tl_slot["x_mm"] + 6,
        top_y_mm=tl_slot["y_mm"],  # full footprint stays inside the slot
        width_mm=tl_slot["width_mm"] - 12,
        axis_color="Brand Deep",
        axis_shade=60,
        label_color="Brand Deep",
        date_color="Ink",
    )
    print(f"  timeline: {len(timeline_items)} items")

    # Comparison table — uses a 32 mm band (3 rows + header)
    tbl_slot = pc.band(height_mm=32)
    await t(
        "create_comparison_table",
        headers=["Backend", "Latency", "Persistent", "GUI", "Best for"],
        rows=[
            ["Headless", "~3 s/call", "no", "none", "CI batch"],
            ["Bridge (Qt)", "~50 ms/call", "yes", "responsive", "Live editing"],
            ["Bridge (no Qt)", "~50 ms/call", "yes", "frozen", "headless persistent"],
        ],
        x_mm=tbl_slot["x_mm"] + 6,
        y_mm=tbl_slot["y_mm"],
        width_mm=tbl_slot["width_mm"] - 12,
        column_widths=[34, 28, 28, 32, 52],
        header_color="Brand Deep",
        cell_color="Ink",
        zebra=True,
        zebra_fill_color="Brand Light",
        zebra_fill_shade=14,
        rule_color="Brand Deep",
    )
    print("  comparison table: 3 rows")

    # Footer at fixed bottom (don't use the cursor — page chrome).
    foot1 = await t("create_text_frame", x_mm=12, y_mm=285, width_mm=186, height_mm=5)
    await t("set_text", name=foot1["name"], text="page 1 of 4 · scribus-mcp showcase")
    await t("set_font_size", name=foot1["name"], size_pt=7)
    await t("set_text_color", name=foot1["name"], color="Subtle")
    await t("set_text_alignment", name=foot1["name"], alignment="center")

    # ===================== PAGE 2 — Showcase =====================
    print("\n=== Page 2: Showcase ===")
    await t("add_page")
    await t("goto_page", page_number=2)

    # Page 2 header
    band2 = await t("create_rectangle", x_mm=0, y_mm=0, width_mm=210, height_mm=22)
    await t("set_fill_color", name=band2["name"], color="Accent")
    await t("set_fill_shade", name=band2["name"], shade_percent=85)
    await t("set_line_color", name=band2["name"], color="None")

    h2 = await t("create_text_frame", x_mm=12, y_mm=6, width_mm=190, height_mm=10)
    await t("set_text", name=h2["name"], text="primitive + pattern showcase")
    await t("set_font_size", name=h2["name"], size_pt=18)
    await t("set_text_color", name=h2["name"], color="White")

    # Body cursor for page 2 — header band ends at y=22, leave 8 mm.
    # default_gap_mm=4 — same auto-spacing convention as page 1.
    pc2 = PageCursor(x_mm=12, y_mm=30, width_mm=186, default_gap_mm=4)

    # Section: shapes — 4 mm label + 18 mm shape band.
    sec_label = await t("create_text_frame", x_mm=12, y_mm=pc2.y, width_mm=186, height_mm=4)
    await t("set_text", name=sec_label["name"], text="SHAPE PRIMITIVES")
    await t("set_font_size", name=sec_label["name"], size_pt=7)
    await t("set_text_color", name=sec_label["name"], color="Brand Deep")
    pc2.gap(7)  # label height + 3 mm

    shape_y = pc2.y  # top of the shape row
    # Rectangle with rounded corners
    rect = await t("create_rectangle", x_mm=12, y_mm=shape_y, width_mm=24, height_mm=18)
    await t("set_fill_color", name=rect["name"], color="Brand Deep")
    await t("set_fill_shade", name=rect["name"], shade_percent=60)
    await t("set_line_color", name=rect["name"], color="None")
    await t("set_corner_radius", name=rect["name"], radius_pt=8)

    ell = await t("create_ellipse", x_mm=42, y_mm=shape_y, width_mm=24, height_mm=18)
    await t("set_fill_color", name=ell["name"], color="Accent")
    await t("set_line_color", name=ell["name"], color="None")

    ln = await t("create_line", x1_mm=72, y1_mm=shape_y, x2_mm=96, y2_mm=shape_y + 18)
    await t("set_line_color", name=ln["name"], color="Ink")
    await t("set_line_width", name=ln["name"], width_pt=2)
    await t("set_line_style", name=ln["name"], style="dash")

    tri = await t("create_polygon", points_mm=[100, shape_y + 18, 124, shape_y + 18, 112, shape_y])
    await t("set_fill_color", name=tri["name"], color="Warm")
    await t("set_line_color", name=tri["name"], color="None")

    pl = await t(
        "create_polyline",
        points_mm=[
            128,
            shape_y + 18,
            134,
            shape_y + 4,
            140,
            shape_y + 13,
            146,
            shape_y + 1,
            152,
            shape_y + 18,
        ],
    )
    await t("set_line_color", name=pl["name"], color="Brand Mid")
    await t("set_line_width", name=pl["name"], width_pt=1.5)

    bz = await t(
        "create_bezier_line",
        points_mm=[
            156,
            shape_y + 18,
            158,
            shape_y - 2,
            168,
            shape_y + 23,
            170,
            shape_y - 2,
            180,
            shape_y + 18,
            182,
            shape_y - 2,
            192,
            shape_y + 23,
            194,
            shape_y - 2,
        ],
    )
    if bz.get("name"):
        await t("set_line_color", name=bz["name"], color="Brand Deep")
        await t("set_line_width", name=bz["name"], width_pt=1.5)
    print("  shapes: rect, ellipse, line, polygon, polyline, bezier")
    pc2.gap(18 + 4)  # past the shape row + 4 mm

    # Section: gradients — 4 mm label + 27 mm body (20 mm swatches + 2 mm gap + 5 mm captions).
    grad_label = await t("create_text_frame", x_mm=12, y_mm=pc2.y, width_mm=186, height_mm=4)
    await t("set_text", name=grad_label["name"], text="GRADIENTS")
    await t("set_font_size", name=grad_label["name"], size_pt=7)
    await t("set_text_color", name=grad_label["name"], color="Brand Deep")
    pc2.gap(6)

    grad_types = ["horizontal", "vertical", "diagonal", "radial"]
    swatch_y = pc2.y
    swatch_w = 36  # narrower swatches → squarer aspect so the radial
    swatch_h = 26  # gradient's center reads as a discrete dot
    swatch_gap = (186 - swatch_w * 4) / 3  # spread evenly across the column
    cap_y = swatch_y + swatch_h + 2
    for i, gt in enumerate(grad_types):
        gx = 12 + int(i * (swatch_w + swatch_gap))
        rect = await t(
            "create_rectangle", x_mm=gx, y_mm=swatch_y, width_mm=swatch_w, height_mm=swatch_h
        )
        # Higher shade contrast (100 → 20) so the radial's dark center is
        # actually visible against the perimeter tint.
        await t(
            "apply_gradient",
            name=rect["name"],
            type=gt,
            color1="Brand Deep",
            color2="Brand Light",
            shade1=100,
            shade2=20,
        )
        await t("set_line_color", name=rect["name"], color="None")
        cap = await t("create_text_frame", x_mm=gx, y_mm=cap_y, width_mm=swatch_w, height_mm=5)
        await t("set_text", name=cap["name"], text=gt)
        await t("set_font_size", name=cap["name"], size_pt=8)
        await t("set_text_color", name=cap["name"], color="Ink")
        await t("set_text_alignment", name=cap["name"], alignment="center")
    print(f"  gradients: {len(grad_types)} types")
    pc2.gap(swatch_h + 2 + 5 + 6)  # swatches + cap gap + cap height + 6 mm spacer

    # Section: markdown import (left ~92 mm) + QR (right ~88 mm) sharing a 96 mm band.
    md_top = pc2.y + 6  # leave 6 mm for section labels above
    md_label = await t("create_text_frame", x_mm=12, y_mm=pc2.y, width_mm=92, height_mm=4)
    await t("set_text", name=md_label["name"], text="MARKDOWN IMPORT")
    await t("set_font_size", name=md_label["name"], size_pt=7)
    await t("set_text_color", name=md_label["name"], color="Brand Deep")

    qr_label = await t("create_text_frame", x_mm=110, y_mm=pc2.y, width_mm=88, height_mm=4)
    await t("set_text", name=qr_label["name"], text="BARCODE / QR")
    await t("set_font_size", name=qr_label["name"], size_pt=7)
    await t("set_text_color", name=qr_label["name"], color="Brand Deep")

    pc2.gap(6)
    await t("import_markdown", markdown_text=MARKDOWN, x_mm=12, y_mm=pc2.y, width_mm=92)
    print("  markdown: imported")

    qr = await t(
        "create_qr_code_block",
        data="https://github.com/caewa/scribus-mcp",
        x_mm=110,
        y_mm=pc2.y,
        size_mm=30,
        caption="caewa/scribus-mcp",
        caption_color="Ink",
        caption_font_size_pt=7,
    )
    print(f"  qr code: ok={qr.get('ok')}")

    # Find/replace right of QR (small box, doesn't push pc2)
    fr_label = await t("create_text_frame", x_mm=145, y_mm=pc2.y + 38, width_mm=53, height_mm=4)
    await t("set_text", name=fr_label["name"], text="FIND / REPLACE")
    await t("set_font_size", name=fr_label["name"], size_pt=7)
    await t("set_text_color", name=fr_label["name"], color="Brand Deep")
    fr = await t("create_text_frame", x_mm=145, y_mm=pc2.y + 44, width_mm=53, height_mm=14)
    await t("set_text", name=fr["name"], text="PLACEHOLDER content")
    await t("set_font_size", name=fr["name"], size_pt=8)
    await t("set_text_color", name=fr["name"], color="Ink")
    rep = await t(
        "find_and_replace_text",
        target="PLACEHOLDER",
        replacement="find/replace works",
        scope="document",
    )
    print(f"  find/replace: {rep.get('replacements')} replacements")

    # The markdown stack is the long pole on the left — heading +
    # paragraph + list end ~70 mm below md_top. Give a 76 mm budget so the
    # bottom row (code_sample + preflight) clears it cleanly.
    pc2.jump_to(md_top + 76)

    # Bottom row: code_sample (left ~92 mm) + preflight summary (right ~88 mm).
    cs_label = await t("create_text_frame", x_mm=12, y_mm=pc2.y, width_mm=92, height_mm=4)
    await t("set_text", name=cs_label["name"], text="SYNTAX-HIGHLIGHTED CODE SAMPLE")
    await t("set_font_size", name=cs_label["name"], size_pt=7)
    await t("set_text_color", name=cs_label["name"], color="Brand Deep")

    preflight = await t("preflight_check")
    issues = (preflight.get("report") or {}).get("issues") or []
    pf_label = await t("create_text_frame", x_mm=110, y_mm=pc2.y, width_mm=88, height_mm=4)
    await t("set_text", name=pf_label["name"], text=f"PREFLIGHT — {len(issues)} issues")
    await t("set_font_size", name=pf_label["name"], size_pt=7)
    await t("set_text_color", name=pf_label["name"], color="Brand Deep")
    pc2.gap(6)

    sample_py = (
        "from scribus_mcp import build_server\n"
        "import asyncio\n"
        "\n"
        "async def main():\n"
        "    mcp = build_server()\n"
        "    out = await mcp.call_tool(\n"
        "        'create_code_sample',\n"
        "        {'code': source, 'language': 'python'})\n"
        "    return out\n"
    )
    await t(
        "create_code_sample",
        code=sample_py,
        language="python",
        x_mm=12,
        y_mm=pc2.y,
        width_mm=92,
        height_mm=42,
        title="example.py",
        title_color="White",
        title_fill_color="Brand Deep",
        font_size_pt=7.5,
        show_line_numbers=True,
        style="default",
        border_color="Brand Deep",
        border_shade=40,
    )

    pf_body = await t("create_text_frame", x_mm=110, y_mm=pc2.y, width_mm=88, height_mm=42)
    if not issues:
        msg = (
            "preflight reports no issues. The page validates: no missing fonts, "
            "no overflowing frames, all images resolved."
        )
    else:
        msg = "Issues found:\n" + "\n".join(
            f"• [{i.get('severity')}] {i.get('kind')} on {i.get('object', '?')}" for i in issues[:5]
        )
    await t("set_text", name=pf_body["name"], text=msg)
    await t("set_font_size", name=pf_body["name"], size_pt=8)
    await t("set_text_color", name=pf_body["name"], color="Ink")
    await t("set_line_spacing", name=pf_body["name"], leading_pt=11)
    print(f"  preflight: {len(issues)} issues")

    # Footer at fixed bottom
    foot2 = await t("create_text_frame", x_mm=12, y_mm=285, width_mm=186, height_mm=5)
    await t(
        "set_text",
        name=foot2["name"],
        text="page 2 of 4 · primitives + gradients + markdown + barcode + code_sample + preflight",
    )
    await t("set_font_size", name=foot2["name"], size_pt=7)
    await t("set_text_color", name=foot2["name"], color="Subtle")
    await t("set_text_alignment", name=foot2["name"], alignment="center")

    # ===================== PAGE 3 — Strip patterns I =====================
    # dark_kpi_band (compact) on top of axes_strip (full-height tall cards
    # with anchor footer). Both are added in 1.1.5; this page is the
    # canonical "strategic decomposition" layout.
    print("\n=== Page 3: Strip patterns I (dark_kpi_band + axes_strip) ===")
    await t("add_page")
    await t("goto_page", page_number=3)

    band3 = await t("create_rectangle", x_mm=0, y_mm=0, width_mm=210, height_mm=22)
    await t("set_fill_color", name=band3["name"], color="Brand Deep")
    await t("set_line_color", name=band3["name"], color="None")

    h3 = await t("create_text_frame", x_mm=12, y_mm=6, width_mm=190, height_mm=10)
    await t("set_text", name=h3["name"], text="strip patterns — dark_kpi_band + axes_strip")
    await t("set_font_size", name=h3["name"], size_pt=18)
    await t("set_text_color", name=h3["name"], color="White")

    pc3 = PageCursor(x_mm=12, y_mm=30, width_mm=186, default_gap_mm=4)

    # Dark KPI band — headline number + breakdown rows with progress bars.
    kpi_band_label = await t(
        "create_text_frame", x_mm=12, y_mm=pc3.y, width_mm=186, height_mm=4
    )
    await t("set_text", name=kpi_band_label["name"], text="DARK KPI BAND")
    await t("set_font_size", name=kpi_band_label["name"], size_pt=7)
    await t("set_text_color", name=kpi_band_label["name"], color="Brand Deep")
    pc3.gap(6)

    band_slot = pc3.band(height_mm=42)
    await t(
        "create_dark_kpi_band",
        title="EMPREINTE FLOTTE 2024-2025 — 244 BATEAUX VENDUS",
        headline_value="117 556",
        headline_caption="tCO2e total (usage)",
        breakdown=[
            {"label": "Carburant",            "value": "73 318 t", "percent": 62, "color": "Warm"},
            {"label": "Électricité",          "value": "18 402 t", "percent": 16, "color": "Brand Mid"},
            {"label": "Maintenance / équip.", "value": "25 836 t", "percent": 22, "color": "Accent"},
        ],
        x_mm=band_slot["x_mm"],
        y_mm=band_slot["y_mm"],
        width_mm=band_slot["width_mm"],
        fill_color="Ink",
        title_color="Accent",
        caption_color="Accent",
        bar_track_color="Brand Light",
        bar_track_shade=30,
    )
    print("  dark_kpi_band: 3-row breakdown")

    # Axes strip — 3 tall cards with colored header + bullets + dark
    # anchor footer. Compress to ~205 mm so it fits the remaining
    # vertical space (we have ~250 mm of content area on this page).
    axes_label = await t(
        "create_text_frame", x_mm=12, y_mm=pc3.y, width_mm=186, height_mm=4
    )
    await t("set_text", name=axes_label["name"], text="AXES STRIP")
    await t("set_font_size", name=axes_label["name"], size_pt=7)
    await t("set_text_color", name=axes_label["name"], color="Brand Deep")
    pc3.gap(6)

    axes_slot = pc3.band(height_mm=205)
    await t(
        "create_axes_strip",
        items=[
            {
                "number": "01",
                "title": "Bateaux\nconnectés",
                "lead": "Architecture numérique propriétaire",
                "items": [
                    "Routeur central et bus CAN maison",
                    "Boîtiers IO normalisés sur 3 séries",
                    "Mise à jour OTA via flotte",
                    "Données télémétrie 1 Hz remontées",
                ],
                "anchor": "MUXEN — Brain 20, Block 8",
                "anchor_eyebrow": "ANCRAGE",
                "accent_color": "Brand Deep",
            },
            {
                "number": "02",
                "title": "Énergie\nbas-carbone",
                "lead": "Mix solaire + lithium dimensionné",
                "items": [
                    "Solaire jusqu'à 6 kWc embarqué",
                    "Banc lithium 30 kWh",
                    "Compteur d'énergie temps réel",
                    "Mode économique automatique",
                ],
                "anchor": "MUXEN — Energy stack",
                "anchor_eyebrow": "ANCRAGE",
                "accent_color": "Accent",
            },
            {
                "number": "03",
                "title": "Service\nlong terme",
                "lead": "10 ans de support garanti",
                "items": [
                    "Diagnostic à distance H+24",
                    "Pièces détachées en stock",
                    "Mise à niveau soft annuelle",
                    "Hotline expert MUXEN",
                ],
                "anchor": "MUXEN — Care & Support",
                "anchor_eyebrow": "ANCRAGE",
                "accent_color": "Warm",
            },
        ],
        x_mm=axes_slot["x_mm"],
        y_mm=axes_slot["y_mm"],
        width_mm=axes_slot["width_mm"],
        height_mm=axes_slot["height_mm"],
        columns=3,
        fill_color="Brand Light",
        fill_shade=18,
        border_color="Brand Mid",
        footer_color="Ink",
    )
    print("  axes_strip: 3 axes with anchor footers")

    foot3 = await t("create_text_frame", x_mm=12, y_mm=285, width_mm=186, height_mm=5)
    await t(
        "set_text",
        name=foot3["name"],
        text="page 3 of 4 · dark_kpi_band + axes_strip — strategy decomposition",
    )
    await t("set_font_size", name=foot3["name"], size_pt=7)
    await t("set_text_color", name=foot3["name"], color="Subtle")
    await t("set_text_alignment", name=foot3["name"], alignment="center")

    # ===================== PAGE 4 — Strip patterns II =====================
    # highlight_card_row (compact) on top of pillar_strip (claim/evidence/
    # narrative pillars). Same release as page 3's patterns.
    print("\n=== Page 4: Strip patterns II (highlight_card_row + pillar_strip) ===")
    await t("add_page")
    await t("goto_page", page_number=4)

    band4 = await t("create_rectangle", x_mm=0, y_mm=0, width_mm=210, height_mm=22)
    await t("set_fill_color", name=band4["name"], color="Brand Deep")
    await t("set_line_color", name=band4["name"], color="None")

    h4 = await t("create_text_frame", x_mm=12, y_mm=6, width_mm=190, height_mm=10)
    await t("set_text", name=h4["name"], text="strip patterns — highlight_card_row + pillar_strip")
    await t("set_font_size", name=h4["name"], size_pt=18)
    await t("set_text_color", name=h4["name"], color="White")

    pc4 = PageCursor(x_mm=12, y_mm=30, width_mm=186, default_gap_mm=4)

    # Highlight card row — 2 cards with bottom strap surfacing one
    # headline metric per series.
    hl_label = await t(
        "create_text_frame", x_mm=12, y_mm=pc4.y, width_mm=186, height_mm=4
    )
    await t("set_text", name=hl_label["name"], text="HIGHLIGHT CARD ROW")
    await t("set_font_size", name=hl_label["name"], size_pt=7)
    await t("set_text_color", name=hl_label["name"], color="Brand Deep")
    pc4.gap(6)

    hl_slot = pc4.band(height_mm=58)
    await t(
        "create_highlight_card_row",
        items=[
            {
                "title": "BALI 5.8 et 5.2",
                "body": (
                    "100 % MUXEN. Taux de retour très limité. La BALI 5.2 est équipée "
                    "de la nouvelle génération du Brain, validée sur 18 mois en mer."
                ),
                "highlight": "1 000+ boîtiers en flotte",
            },
            {
                "title": "YOT 50",
                "body": (
                    "Reprend la même architecture validée que la BALI 5.2 — câblage, "
                    "boîtiers IO, supervision. Mise en série prévue T3 2026."
                ),
                "highlight": "Architecture transposée",
            },
        ],
        x_mm=hl_slot["x_mm"],
        y_mm=hl_slot["y_mm"],
        width_mm=hl_slot["width_mm"],
        height_mm=hl_slot["height_mm"],
        columns=2,
        accent_color="Accent",
    )
    print("  highlight_card_row: 2 series cards")

    # Pillar strip — 3 austere white pillars with proofs + narrative.
    pillar_label = await t(
        "create_text_frame", x_mm=12, y_mm=pc4.y, width_mm=186, height_mm=4
    )
    await t("set_text", name=pillar_label["name"], text="PILLAR STRIP")
    await t("set_font_size", name=pillar_label["name"], size_pt=7)
    await t("set_text_color", name=pillar_label["name"], color="Brand Deep")
    pc4.gap(6)

    pillar_slot = pc4.band(height_mm=185)
    await t(
        "create_pillar_strip",
        items=[
            {
                "number": "01",
                "title": "Solidité\ntechnologique",
                "lead": "Un actif R&D propriétaire",
                "proofs": [
                    ["> 1 000",  "boîtiers en flotte"],
                    ["< 0,5 %",  "taux SAV résiduel"],
                    ["2 séries", "100 % MUXEN"],
                ],
                "body": (
                    "Plateforme HW propriétaire. 95 % des tickets SAV liés à des "
                    "facteurs tiers (cellules, capteurs externes). Roadmap soft "
                    "alignée sur 3 ans."
                ),
                "accent_color": "Brand Deep",
            },
            {
                "number": "02",
                "title": "Industrialisation\nmaîtrisée",
                "lead": "Un partenariat ACS-Cetex",
                "proofs": [
                    ["3 lignes", "production active"],
                    ["MUXEN-CEM", "compliance EMC"],
                    ["ISO 9001", "qualité tracée"],
                ],
                "body": (
                    "Partenaire industriel co-investisseur depuis 2022. Capacité "
                    "scalable à 5 000 unités/an sans CAPEX additionnel."
                ),
                "accent_color": "Accent",
            },
            {
                "number": "03",
                "title": "Service\nlong terme",
                "lead": "Hotline + diagnostic à distance",
                "proofs": [
                    ["10 ans",   "support garanti"],
                    ["H + 24",   "intervention max"],
                    ["3 hubs",   "France · Asie · USA"],
                ],
                "body": (
                    "Centre de service multi-zones. Pièces détachées en stock. "
                    "Mise à niveau soft annuelle gratuite pour la flotte active."
                ),
                "accent_color": "Warm",
            },
        ],
        x_mm=pillar_slot["x_mm"],
        y_mm=pillar_slot["y_mm"],
        width_mm=pillar_slot["width_mm"],
        height_mm=pillar_slot["height_mm"],
        columns=3,
        fill_color="White",
    )
    print("  pillar_strip: 3 pillars with proofs + body")

    foot4 = await t("create_text_frame", x_mm=12, y_mm=285, width_mm=186, height_mm=5)
    await t(
        "set_text",
        name=foot4["name"],
        text="page 4 of 4 · highlight_card_row + pillar_strip — claim · evidence · narrative",
    )
    await t("set_font_size", name=foot4["name"], size_pt=7)
    await t("set_text_color", name=foot4["name"], color="Subtle")
    await t("set_text_alignment", name=foot4["name"], alignment="center")

    # ===================== Save + Export =====================
    print("\n=== Save + Export ===")
    save = await t("save_document_as", path=SLA)
    print(f"  save sla: ok={save.get('ok')}")
    pdf = await t("export_pdf", path=PDF, pages="all", resolution=200)
    print(f"  export pdf: ok={pdf.get('ok')} value={pdf.get('value')}")

    # Render previews via render_page_to_image and write them next to
    # the .sla / .pdf so the repo always carries up-to-date PNGs.
    import base64

    print("\n=== Render previews ===")
    for pn in (1, 2, 3, 4):
        out = await mcp.call_tool(
            "render_page_to_image",
            {"page_number": pn, "dpi": 110, "mode": MODE},
        )
        content = out[0] if isinstance(out, tuple) else out
        if isinstance(content, list):
            for c in content:
                if getattr(c, "type", None) == "image":
                    data = base64.b64decode(getattr(c, "data", ""))
                    fn = str(OUT_DIR / f"showcase-p{pn}.png")
                    with open(fn, "wb") as f:
                        f.write(data)
                    print(f"  page {pn}: wrote {fn} ({len(data)} bytes)")

    print("\nDone:")
    print(f"  SLA: {SLA}")
    print(f"  PDF: {PDF}")


asyncio.run(main())

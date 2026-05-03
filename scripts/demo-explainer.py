"""5-page self-explainer document for scribus-mcp.

This is a real document — the kind a stakeholder would actually read —
that explains what the MCP is, what it does, and how to use it. Doubles
as a stress test for multi-page consistency and combining most patterns.

  Page 1 — Cover / TL;DR
  Page 2 — Architecture
  Page 3 — Tool surface
  Page 4 — Use cases
  Page 5 — Getting started

Outputs:
  C:/Users/William/scribus-mcp/explainer.sla
  C:/Users/William/scribus-mcp/explainer.pdf
"""

from __future__ import annotations

import asyncio

from scribus_mcp.layout import PageCursor
from scribus_mcp.server import build_server
from scribus_mcp.testing import unwrap

SLA = "C:/Users/William/scribus-mcp/explainer.sla"
PDF = "C:/Users/William/scribus-mcp/explainer.pdf"
MODE = "interactive"
TOTAL_PAGES = 5


# ---------------------------------------------------------------------------
# Page chrome — header band + footer; called for every page so master-page
# styling is consistent without actually editing a master page.
# ---------------------------------------------------------------------------


async def page_chrome(t, page_num: int, accent: str, title: str):
    """Header band + footer. Call once per page.

    Page-number marks: Scribus 1.7's Scripter API does not expose auto
    page-number fields (no `insertMark`, no special-character variable),
    so we stamp the number passed in. If pages get reordered later, the
    chrome will need to be re-stamped — re-run this demo script.
    """
    # Header — single tool call replaces the four-frame hand-roll.
    await t(
        "create_hero_band",
        title=title,
        eyebrow=f"PAGE {page_num} OF {TOTAL_PAGES}",
        right_text="scribus-mcp · v1.0.0",
        x_mm=0,
        y_mm=0,
        width_mm=210,
        height_mm=18,
        fill_color=accent,
        title_font_size_pt=14,
        eyebrow_font_size_pt=7,
        right_font_size_pt=8,
        padding_x_mm=12,
        padding_y_mm=4,
    )

    # Thin accent rule above footer
    rule = await t("create_rectangle", x_mm=12, y_mm=283, width_mm=186, height_mm=0.4)
    await t("set_fill_color", name=rule["name"], color=accent)
    await t("set_fill_shade", name=rule["name"], shade_percent=40)
    await t("set_line_color", name=rule["name"], color="None")

    # Footer
    foot = await t("create_text_frame", x_mm=12, y_mm=287, width_mm=186, height_mm=5)
    await t(
        "set_text",
        name=foot["name"],
        text=f"scribus-mcp · self-explainer · page {page_num} / {TOTAL_PAGES}",
    )
    await t("set_font_size", name=foot["name"], size_pt=7)
    await t("set_text_color", name=foot["name"], color="Ink")
    await t("set_text_alignment", name=foot["name"], alignment="center")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


async def build_page1(t):
    """Cover / TL;DR."""
    await page_chrome(t, 1, accent="Brand Deep", title="What is scribus-mcp?")

    # Body cursor: header chrome ends at y=18, leave 12 mm.
    # default_gap_mm=4 — auto-inserted vertical breathing room between bands.
    pc = PageCursor(x_mm=12, y_mm=30, width_mm=186, default_gap_mm=4)

    # Big hero title — tighter than the default gap (only 2 mm to subhead).
    hero_slot = pc.band(height_mm=22, gap_mm=2)
    hero = await t(
        "create_text_frame", **{k: hero_slot[k] for k in ("x_mm", "y_mm", "width_mm", "height_mm")}
    )
    await t("set_text", name=hero["name"], text="Drive Scribus from Claude.")
    await t("set_font_size", name=hero["name"], size_pt=28)
    await t("set_text_color", name=hero["name"], color="Brand Deep")

    # Subhead paragraph — extra 6 mm gap before the KPI band.
    sub_slot = pc.band(height_mm=18, gap_mm=6)
    sub = await t(
        "create_text_frame", **{k: sub_slot[k] for k in ("x_mm", "y_mm", "width_mm", "height_mm")}
    )
    await t(
        "set_text",
        name=sub["name"],
        text=(
            "scribus-mcp is a Model Context Protocol server that wraps the Scribus 1.7 "
            "Scripter API. Claude uses it to compose, style, and export desktop-publishing "
            "documents — through a live Scribus window or a one-shot headless invocation."
        ),
    )
    await t("set_font_size", name=sub["name"], size_pt=11)
    await t("set_text_color", name=sub["name"], color="Ink")
    await t("set_text_alignment", name=sub["name"], alignment="justify")
    await t("set_line_spacing", name=sub["name"], leading_pt=15)

    # KPI tiles row — extra 6 mm gap before the pillar grid.
    await t(
        "create_kpi_row",
        items=[
            {
                "value": "125",
                "label": "MCP tools",
                "delta": "across 17 modules",
                "fill_color": "Brand Deep",
                "label_color": "Brand Deep",
            },
            {
                "value": "136",
                "label": "tests passing",
                "delta": "Phase 1 + 2 green",
                "fill_color": "Brand Mid",
                "label_color": "Brand Mid",
            },
            {
                "value": "2",
                "label": "backends",
                "delta": "headless + interactive",
                "fill_color": "Accent",
                "label_color": "Accent",
            },
            {
                "value": "0",
                "label": "external services",
                "delta": "stdlib + scribus only",
                "fill_color": "Warm",
                "label_color": "Warm",
            },
        ],
        **pc.band(height_mm=38, gap_mm=6),
        gap_mm=3,
        value_color="Ink",
        value_font_size_pt=24,
        delta_color="Ink",
    )

    # Three pillars (callout boxes) — split the band 3 ways with 3 mm gaps.
    pillars = [
        (
            "Composable",
            "All MCP primitives — Tools, Resources, Prompts — are first-class. Claude "
            "discovers them, calls them, and gets typed JSON back.",
        ),
        (
            "Live or batched",
            "Two interchangeable backends: persistent bridge inside a running Scribus, "
            "or a fresh headless spawn per call. Auto-selected.",
        ),
        (
            "Pattern-rich",
            "High-level tools cover charts, callouts, KPIs, tables, QR codes, syntax-highlighted "
            "code blocks, layouts, and Markdown import — one call replaces dozens of primitives.",
        ),
    ]
    pw = 60  # 60 + 3 + 60 + 3 + 60 = 186 mm exactly
    # extra 8 mm vertical gap before the decorative band.
    pillar_slots = pc.split(widths_mm=[pw, pw, pw], inner_gap_mm=3, height_mm=46, gap_mm=8)
    for slot, (title, body) in zip(pillar_slots, pillars, strict=False):
        await t(
            "create_callout_box",
            title=title,
            body=body,
            x_mm=slot["x_mm"],
            y_mm=slot["y_mm"],
            width_mm=slot["width_mm"],
            height_mm=slot["height_mm"],
            fill_color="Brand Light",
            fill_shade=15,
            border_color="Brand Mid",
            border_shade=50,
            title_color="Brand Deep",
            body_color="Ink",
        )

    # Decorative geometric flourish — three shapes spread across the column.
    # Extra 12 mm before the closing tagline.
    deco_slot = pc.band(height_mm=40, gap_mm=12)
    deco_y = deco_slot["y_mm"]
    e1 = await t("create_ellipse", x_mm=20, y_mm=deco_y, width_mm=40, height_mm=40)
    await t("set_fill_color", name=e1["name"], color="Brand Deep")
    await t("set_fill_shade", name=e1["name"], shade_percent=15)
    await t("set_line_color", name=e1["name"], color="None")
    tri = await t("create_polygon", points_mm=[80, deco_y + 40, 120, deco_y + 40, 100, deco_y])
    await t("set_fill_color", name=tri["name"], color="Accent")
    await t("set_fill_shade", name=tri["name"], shade_percent=22)
    await t("set_line_color", name=tri["name"], color="None")
    rr = await t("create_rectangle", x_mm=140, y_mm=deco_y, width_mm=50, height_mm=40)
    await t("set_fill_color", name=rr["name"], color="Brand Mid")
    await t("set_fill_shade", name=rr["name"], shade_percent=22)
    await t("set_line_color", name=rr["name"], color="None")
    await t("set_corner_radius", name=rr["name"], radius_pt=20)

    # Tagline below decorations
    tag_slot = pc.band(height_mm=10)
    tag = await t(
        "create_text_frame", **{k: tag_slot[k] for k in ("x_mm", "y_mm", "width_mm", "height_mm")}
    )
    await t(
        "set_text",
        name=tag["name"],
        text="Read on for the architecture, the tool surface, and how to install it.",
    )
    await t("set_font_size", name=tag["name"], size_pt=11)
    await t("set_text_color", name=tag["name"], color="Brand Deep")
    await t("set_text_alignment", name=tag["name"], alignment="center")


async def build_page2(t):
    """Architecture."""
    await page_chrome(t, 2, accent="Brand Mid", title="Architecture")

    # Intro paragraph
    intro = await t("create_text_frame", x_mm=12, y_mm=28, width_mm=186, height_mm=20)
    await t(
        "set_text",
        name=intro["name"],
        text=(
            "One Python server speaks MCP to the client and Scripter to Scribus. "
            "Two backends sit behind a single tool surface — chosen per call, with sensible defaults."
        ),
    )
    await t("set_font_size", name=intro["name"], size_pt=10)
    await t("set_text_color", name=intro["name"], color="Ink")
    await t("set_line_spacing", name=intro["name"], leading_pt=14)

    # Architecture diagram drawn from primitives
    diag_y = 54
    # Boxes
    boxes = [
        ("Claude / IDE", 12, diag_y, 50, 18, "Brand Deep"),
        ("scribus-mcp\n(Python 3.11+)", 80, diag_y, 50, 18, "Brand Mid"),
        ("Scribus 1.7\n(Scripter API)", 148, diag_y, 50, 18, "Accent"),
    ]
    box_names = []
    for label, bx, by, bw, bh, col in boxes:
        rect = await t("create_rectangle", x_mm=bx, y_mm=by, width_mm=bw, height_mm=bh)
        rn = rect["name"]
        box_names.append(rn)
        await t("set_fill_color", name=rn, color=col)
        await t("set_fill_shade", name=rn, shade_percent=18)
        await t("set_line_color", name=rn, color=col)
        await t("set_line_shade", name=rn, shade_percent=80)
        await t("set_line_width", name=rn, width_pt=0.6)
        await t("set_corner_radius", name=rn, radius_pt=4)
        # Label
        lab = await t(
            "create_text_frame",
            x_mm=bx + 2,
            y_mm=by + 4,
            width_mm=bw - 4,
            height_mm=bh - 4,
        )
        await t("set_text", name=lab["name"], text=label)
        await t("set_font_size", name=lab["name"], size_pt=10)
        await t("set_text_color", name=lab["name"], color="Ink")
        await t("set_text_alignment", name=lab["name"], alignment="center")

    # Arrows (lines with line_cap)
    arrow_y = diag_y + 9
    a1 = await t("create_line", x1_mm=62, y1_mm=arrow_y, x2_mm=80, y2_mm=arrow_y)
    await t("set_line_color", name=a1["name"], color="Brand Deep")
    await t("set_line_width", name=a1["name"], width_pt=1.4)
    await t("set_line_cap", name=a1["name"], cap="round")

    a2 = await t("create_line", x1_mm=130, y1_mm=arrow_y, x2_mm=148, y2_mm=arrow_y)
    await t("set_line_color", name=a2["name"], color="Brand Mid")
    await t("set_line_width", name=a2["name"], width_pt=1.4)
    await t("set_line_cap", name=a2["name"], cap="round")

    # Captions ABOVE the arrows so they're not obscured by the arrow line
    cap1 = await t("create_text_frame", x_mm=60, y_mm=arrow_y - 5, width_mm=22, height_mm=4)
    await t("set_text", name=cap1["name"], text="MCP")
    await t("set_font_size", name=cap1["name"], size_pt=8)
    await t("set_text_color", name=cap1["name"], color="Brand Deep")
    await t("set_text_alignment", name=cap1["name"], alignment="center")

    cap2 = await t("create_text_frame", x_mm=126, y_mm=arrow_y - 5, width_mm=24, height_mm=4)
    await t("set_text", name=cap2["name"], text="TCP / -py")
    await t("set_font_size", name=cap2["name"], size_pt=8)
    await t("set_text_color", name=cap2["name"], color="Brand Mid")
    await t("set_text_alignment", name=cap2["name"], alignment="center")

    # Two-backend comparison side by side
    sec_label = await t("create_text_frame", x_mm=12, y_mm=88, width_mm=186, height_mm=4)
    await t("set_text", name=sec_label["name"], text="TWO BACKENDS, ONE TOOL SURFACE")
    await t("set_font_size", name=sec_label["name"], size_pt=7)
    await t("set_text_color", name=sec_label["name"], color="Brand Deep")

    await t(
        "create_callout_box",
        title="Headless",
        body=(
            "Spawn `scribus -g -ns -py /tmp/job.py` per call. Stateless, ~3 s per spawn. "
            "Best for batch jobs and CI: generate manuals, briefs, and PDFs unattended."
        ),
        x_mm=12,
        y_mm=96,
        width_mm=92,
        height_mm=42,
        fill_color="Brand Light",
        fill_shade=18,
        border_color="Brand Mid",
        border_shade=50,
        title_color="Brand Mid",
    )

    await t(
        "create_callout_box",
        title="Interactive bridge",
        body=(
            "A small .spy script inside a running Scribus listens on TCP loopback. The "
            "MCP dispatches calls onto Scribus's Qt main thread via QTimer. ~50 ms per "
            "call. Best for live editing assistance — Claude composes while you watch."
        ),
        x_mm=110,
        y_mm=96,
        width_mm=88,
        height_mm=42,
        fill_color="Brand Light",
        fill_shade=18,
        border_color="Brand Mid",
        border_shade=50,
        title_color="Brand Mid",
    )

    # Comparison table
    tbl_label = await t("create_text_frame", x_mm=12, y_mm=146, width_mm=186, height_mm=4)
    await t("set_text", name=tbl_label["name"], text="BACKEND COMPARISON")
    await t("set_font_size", name=tbl_label["name"], size_pt=7)
    await t("set_text_color", name=tbl_label["name"], color="Brand Deep")

    await t(
        "create_comparison_table",
        headers=["Aspect", "Headless", "Interactive bridge"],
        rows=[
            ["Latency / call", "~3 s", "~50 ms"],
            ["Persistence", "stateless", "doc state preserved"],
            ["GUI", "none", "responsive (with Qt binding)"],
            ["Best for", "CI batch", "live editing"],
            ["Discovery", "spawn", "JSON discovery file + token"],
            ["Failure mode", "process exits", "tool returns ok=false"],
        ],
        x_mm=12,
        y_mm=154,
        width_mm=186,
        column_widths=[42, 60, 84],
        header_color="Brand Deep",
        cell_color="Ink",
        zebra=True,
        zebra_fill_color="Brand Light",
        zebra_fill_shade=14,
        rule_color="Brand Deep",
    )

    # Health radar
    radar_label = await t("create_text_frame", x_mm=12, y_mm=216, width_mm=92, height_mm=4)
    await t("set_text", name=radar_label["name"], text="WHERE WE ARE")
    await t("set_font_size", name=radar_label["name"], size_pt=7)
    await t("set_text_color", name=radar_label["name"], color="Brand Deep")

    await t(
        "create_radar_chart",
        axes=["Coverage", "Speed", "Reliability", "DX", "Docs", "UX"],
        values=[0.95, 0.85, 0.9, 0.8, 0.7, 0.75],
        center_x_mm=58,
        center_y_mm=250,
        radius_mm=22,
        ring_color="Ink",
        ring_shade=18,
        axis_color="Ink",
        axis_shade=30,
        data_fill_color="Brand Mid",
        data_fill_shade=22,
        data_line_color="Brand Mid",
        data_line_width_pt=1.4,
        label_color="Ink",
    )

    # Right of radar: explanation
    exp = await t("create_text_frame", x_mm=110, y_mm=224, width_mm=88, height_mm=50)
    await t(
        "set_text",
        name=exp["name"],
        text=(
            "Coverage and reliability come from 85 integration tests against a live Scribus, "
            "ABI-matched PyQt6 install for interactive mode, and per-tool error paths that "
            "surface as {ok: false, error: …} for the model to self-correct.\n\n"
            "Documentation and UX are still maturing: the patterns library will keep growing."
        ),
    )
    await t("set_font_size", name=exp["name"], size_pt=9)
    await t("set_text_color", name=exp["name"], color="Ink")
    await t("set_text_alignment", name=exp["name"], alignment="justify")
    await t("set_line_spacing", name=exp["name"], leading_pt=12)


async def build_page3(t):
    """Tool surface."""
    await page_chrome(t, 3, accent="Accent", title="What you can call")

    intro = await t("create_text_frame", x_mm=12, y_mm=28, width_mm=186, height_mm=14)
    await t(
        "set_text",
        name=intro["name"],
        text=(
            "Tools are grouped by domain. Each one returns a structured dict so Claude "
            "can reason about success, failure, and any object names it created."
        ),
    )
    await t("set_font_size", name=intro["name"], size_pt=10)
    await t("set_text_color", name=intro["name"], color="Ink")
    await t("set_line_spacing", name=intro["name"], leading_pt=14)

    # Distribution chart (categories)
    chart_label = await t("create_text_frame", x_mm=12, y_mm=46, width_mm=92, height_mm=4)
    await t("set_text", name=chart_label["name"], text="TOOL DISTRIBUTION")
    await t("set_font_size", name=chart_label["name"], size_pt=7)
    await t("set_text_color", name=chart_label["name"], color="Brand Deep")

    # Tool counts per category (rough; reflect 125-tool surface as of v0.1).
    cat_labels = [
        "Doc/Pages",
        "Frames/Text",
        "Shape/Style",
        "Patterns",
        "Layouts",
        "Forms",
        "Fonts",
        "Other",
    ]
    cat_values = [14, 22, 22, 11, 11, 13, 7, 25]

    await t(
        "create_pie_chart",
        labels=cat_labels,
        values=cat_values,
        center_x_mm=42,
        center_y_mm=82,
        radius_mm=22,
        colors=[
            "Brand Deep",
            "Brand Mid",
            "Accent",
            "Warm",
            "Brand Light",
            "Subtle",
            "Brand Deep",
            "Brand Mid",
        ],
        outline_color="None",
        outer_ring_color="White",
        outer_ring_width_pt=0.7,
        label_color="Ink",
    )

    # Bar chart of tools per category (right)
    bar_label = await t("create_text_frame", x_mm=110, y_mm=46, width_mm=88, height_mm=4)
    await t("set_text", name=bar_label["name"], text="TOOLS PER CATEGORY")
    await t("set_font_size", name=bar_label["name"], size_pt=7)
    await t("set_text_color", name=bar_label["name"], color="Brand Deep")

    await t(
        "create_bar_chart",
        labels=["Doc", "Frame", "Shape", "Patt", "Layt", "Form", "Font", "Etc"],
        values=cat_values,
        x_mm=110,
        y_mm=54,
        width_mm=88,
        height_mm=46,
        bar_color="Accent",
        bar_shade=80,
        gridline_color="Ink",
        gridline_shade=15,
        label_color="Ink",
        show_values=True,
    )

    # Pattern callouts grid (3 wide × 2 tall)
    pat_label = await t("create_text_frame", x_mm=12, y_mm=128, width_mm=186, height_mm=4)
    await t("set_text", name=pat_label["name"], text="HIGH-LEVEL PATTERNS — ONE CALL EACH")
    await t("set_font_size", name=pat_label["name"], size_pt=7)
    await t("set_text_color", name=pat_label["name"], color="Brand Deep")

    patterns = [
        (
            "create_code_sample",
            "Pygments syntax-highlighted code block with monospace font + per-token color.",
        ),
        (
            "create_radar_chart",
            "N-axis polar chart with concentric rings, axis labels, and a data overlay polygon.",
        ),
        ("create_bar_chart", "Vertical bars with gridlines, optional value labels above each bar."),
        ("create_pie_chart", "Polygon-approximated slices with legend + clean outer ring."),
        ("create_timeline", "Horizontal axis + tick marks + label-above + optional date-below."),
        ("create_callout_box", "Bordered, lightly shaded box with title and justified body."),
        (
            "create_kpi_row",
            "Auto-laid row of KPI tiles — pass items, get an evenly-spaced row back.",
        ),
        ("create_card_grid", "2-D grid of accent-bordered cards with eyebrow / title / body."),
        (
            "create_qr_code_block",
            "QR / EAN13 / Code128 / Data Matrix via Scribus's BWIPP, optional caption.",
        ),
    ]
    cw = 60
    ch = 26
    cx0 = 12
    cy0 = 138
    cgap = 3
    for i, (name, desc) in enumerate(patterns):
        col = i % 3
        row = i // 3
        x = cx0 + col * (cw + cgap)
        y = cy0 + row * (ch + cgap)
        await t(
            "create_callout_box",
            title=name,
            body=desc,
            x_mm=x,
            y_mm=y,
            width_mm=cw,
            height_mm=ch,
            fill_color="Subtle",
            fill_shade=20,
            border_color="Accent",
            border_shade=70,
            border_width_pt=0.4,
            title_color="Accent",
            title_font_size_pt=9,
            body_color="Ink",
            body_font_size_pt=8,
            padding_mm=2.8,
            title_height_mm=4,
        )


async def build_page4(t):
    """Use cases."""
    await page_chrome(t, 4, accent="Warm", title="Where this fits")

    intro = await t("create_text_frame", x_mm=12, y_mm=28, width_mm=186, height_mm=14)
    await t(
        "set_text",
        name=intro["name"],
        text=(
            "Anywhere you generate or maintain print-quality documents — and want an LLM "
            "to do it without inventing geometry or writing PostScript by hand."
        ),
    )
    await t("set_font_size", name=intro["name"], size_pt=10)
    await t("set_text_color", name=intro["name"], color="Ink")
    await t("set_line_spacing", name=intro["name"], leading_pt=14)

    # 4 use-case cards in a 2×2 grid. accent_side varies per card to show
    # the chrome works on any edge. ~100 lines of hand-rolled layout
    # collapsed into a single tool call thanks to create_card_grid.
    sides = ["left", "top", "right", "bottom"]
    cases = [
        (
            "Product manuals",
            "Brain20 / hardware",
            "Convert a Markdown spec + a parts CSV into a styled, indexed user manual. "
            "Headless mode runs unattended in CI; PDF/X-4 output is print-ready.",
            "Brand Deep",
        ),
        (
            "Brief documents",
            "Internal one-pagers",
            "Database schemas, deployment briefs, postmortems. The MCP composes "
            "headers, KPI tiles, comparison tables, and code blocks from a structured prompt.",
            "Brand Mid",
        ),
        (
            "Dashboards & reports",
            "Periodic deliverables",
            "Weekly KPI snapshots, sales reports, status updates. Pie / bar / radar / "
            "timeline patterns — one tool call per chart, parameterised by your data.",
            "Accent",
        ),
        (
            "Marketing collateral",
            "Datasheets, flyers",
            "Templated cards, pitch decks rendered as PDFs, datasheets with auto-generated "
            "QR codes that link to per-product pages. Same MCP, different prompt.",
            "Warm",
        ),
    ]
    items = [
        {
            "title": title,
            "body": body,
            "eyebrow": f"{sub} · accent: {sides[i]}",
            "accent_color": accent,
            "accent_side": sides[i],
            "title_color": accent,
            "eyebrow_color": accent,
            "border_color": accent,
            "border_shade": 40,
        }
        for i, (title, sub, body, accent) in enumerate(cases)
    ]
    await t(
        "create_card_grid",
        items=items,
        x_mm=12,
        y_mm=50,
        width_mm=186,
        height_mm=144,
        columns=2,
        column_gap_mm=4,
        row_gap_mm=4,
        accent_thickness_mm=1.6,
        fill_color="Brand Light",
        fill_shade=22,
        border_width_pt=0.5,
        corner_radius_pt=6,
        title_font_size_pt=15,
        body_color="Ink",
        body_font_size_pt=9,
        body_line_spacing_pt=12,
        padding_mm=6,
    )

    # Bottom strip — timeline of when each use case applies
    tl_label = await t("create_text_frame", x_mm=12, y_mm=210, width_mm=186, height_mm=4)
    await t("set_text", name=tl_label["name"], text="WHERE THIS PROJECT IS HEADED")
    await t("set_font_size", name=tl_label["name"], size_pt=7)
    await t("set_text_color", name=tl_label["name"], color="Brand Deep")

    await t(
        "create_timeline",
        items=[
            {"position": 0.0, "label": "v0.1 alpha", "date": "May 2026"},
            {"position": 0.25, "label": "Linux validated", "date": "Q2"},
            {"position": 0.5, "label": "More patterns", "date": "Q3"},
            {"position": 0.75, "label": "Style libraries", "date": "Q4"},
            {"position": 1.0, "label": "v1.0", "date": "2027"},
        ],
        x_mm=18,
        axis_y_mm=224,
        width_mm=174,
        axis_color="Brand Deep",
        axis_shade=60,
        label_color="Brand Deep",
        date_color="Ink",
    )

    # Note about open-source
    note = await t("create_text_frame", x_mm=12, y_mm=246, width_mm=186, height_mm=20)
    await t(
        "set_text",
        name=note["name"],
        text=(
            "MIT-licensed and source-available. Patterns add as much value as primitives — "
            "if your team has a recurring layout, contributing it as a single tool benefits "
            "every other user. The repository link is on the next page."
        ),
    )
    await t("set_font_size", name=note["name"], size_pt=8)
    await t("set_text_color", name=note["name"], color="Ink")
    await t("set_text_alignment", name=note["name"], alignment="center")


async def build_page5(t):
    """Getting started."""
    await page_chrome(t, 5, accent="Brand Deep", title="Getting started")

    intro = await t("create_text_frame", x_mm=12, y_mm=28, width_mm=186, height_mm=10)
    await t(
        "set_text",
        name=intro["name"],
        text="Three steps from zero to a Scribus driven by Claude.",
    )
    await t("set_font_size", name=intro["name"], size_pt=11)
    await t("set_text_color", name=intro["name"], color="Brand Deep")
    await t("set_text_alignment", name=intro["name"], alignment="center")

    steps = [
        {
            "title": "Install Scribus + the MCP",
            "body": (
                "Scribus 1.7.x from scribus.net; the MCP via `pip install -e .` in a "
                "Python 3.11+ venv. Verify with `scribus-mcp --help`."
            ),
        },
        {
            "title": "(Optional) Enable the live bridge",
            "body": (
                "Linux: `apt install python3-pyqt6` (system Python). Windows: run "
                "`scripts/install-pyqt-windows.ps1` as administrator — auto-detects "
                "Scribus's Qt minor version and pins a matching PyQt6."
            ),
        },
        {
            "title": "Wire it into Claude Code",
            "body": (
                "Add `scribus-mcp` to your MCP server config. Open Scribus + the bridge, "
                'or let Claude call tools with `mode="headless"` (no Scribus needed).'
            ),
        },
    ]
    # Single tool call replaces the for-loop hand-rolling 6 frames per step.
    await t(
        "create_numbered_steps",
        items=steps,
        x_mm=12,
        y_mm=44,
        width_mm=186,
        item_height_mm=36,
        gap_mm=6,
        badge_diameter_mm=12,
        badge_fill_color="Brand Deep",
        badge_text_color="White",
        badge_text_font_size_pt=14,
        body_fill_color="Brand Light",
        body_fill_shade=15,
        body_border_color="Brand Mid",
        body_border_shade=50,
        title_color="Brand Deep",
        body_text_color="Ink",
    )

    # Code example — dogfood the new create_code_sample pattern.
    md_label = await t("create_text_frame", x_mm=12, y_mm=174, width_mm=186, height_mm=4)
    await t("set_text", name=md_label["name"], text="HELLO WORLD — MINIMAL EXAMPLE")
    await t("set_font_size", name=md_label["name"], size_pt=7)
    await t("set_text_color", name=md_label["name"], color="Brand Deep")

    sample_code = (
        "{\n"
        '    "mcpServers": {\n'
        '        "scribus": {\n'
        '            "command": "scribus-mcp",\n'
        '            "env": { "SCRIBUS_BIN": "/usr/bin/scribus" }\n'
        "        }\n"
        "    }\n"
        "}\n"
    )
    await t(
        "create_code_sample",
        code=sample_code,
        language="json",
        x_mm=12,
        y_mm=180,
        width_mm=186,
        height_mm=46,
        title="claude-mcp-config.json",
        title_color="White",
        title_fill_color="Brand Deep",
        font_size_pt=9,
        show_line_numbers=True,
        style="default",
        border_color="Brand Deep",
        border_shade=40,
    )

    # QR + repo link at bottom
    repo_label = await t("create_text_frame", x_mm=12, y_mm=232, width_mm=186, height_mm=4)
    await t("set_text", name=repo_label["name"], text="REPOSITORY")
    await t("set_font_size", name=repo_label["name"], size_pt=7)
    await t("set_text_color", name=repo_label["name"], color="Brand Deep")

    await t(
        "create_qr_code_block",
        data="https://github.com/caewa/scribus-mcp",
        x_mm=84,
        y_mm=240,
        size_mm=30,
        caption="caewa/scribus-mcp",
        caption_color="Ink",
        caption_font_size_pt=8,
    )

    # Closing line below the QR
    closing = await t("create_text_frame", x_mm=12, y_mm=276, width_mm=186, height_mm=6)
    await t(
        "set_text",
        name=closing["name"],
        text="Generated by scribus-mcp itself — every page on this PDF.",
    )
    await t("set_font_size", name=closing["name"], size_pt=8)
    await t("set_text_color", name=closing["name"], color="Ink")
    await t("set_text_alignment", name=closing["name"], alignment="center")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    mcp = build_server()

    async def t(_tool, **kwargs):
        kwargs.setdefault("mode", MODE)
        return unwrap(await mcp.call_tool(_tool, kwargs))

    print("=== Setup ===")
    await t("close_document")
    r = await t(
        "create_document",
        width_mm=210,
        height_mm=297,
        margin_top_mm=12,
        margin_left_mm=12,
        margin_right_mm=12,
        margin_bottom_mm=12,
    )
    print(f"  document: ok={r.get('ok')}")

    palette = [
        ("Brand Deep", 85, 55, 0, 10),
        ("Brand Mid", 65, 30, 0, 0),
        ("Brand Light", 35, 8, 0, 0),
        ("Accent", 0, 70, 85, 0),
        ("Warm", 5, 35, 70, 0),
        ("Ink", 0, 0, 0, 85),
        ("Subtle", 0, 0, 0, 12),
    ]
    for name, c, m, y, k in palette:
        await t("define_color_cmyk", name=name, cyan=c, magenta=m, yellow=y, key=k)
    print(f"  palette: {len(palette)} colors")

    # Build page 1 (already on page 1 from create_document)
    print("\n=== Page 1: cover ===")
    await build_page1(t)

    # Add and switch to each subsequent page
    for pn, builder in enumerate([build_page2, build_page3, build_page4, build_page5], start=2):
        print(f"\n=== Page {pn} ===")
        await t("add_page")
        await t("goto_page", page_number=pn)
        await builder(t)

    # Save + export
    print("\n=== Save + Export ===")
    save = await t("save_document_as", path=SLA)
    print(f"  save sla: ok={save.get('ok')}")
    pdf = await t("export_pdf", path=PDF, pages="all", resolution=200)
    print(f"  export pdf: ok={pdf.get('ok')} pages={pdf.get('value', {}).get('pages_exported')}")

    pf = await t("preflight_check")
    issues = (pf.get("report") or {}).get("issues") or []
    print(f"  preflight: {len(issues)} issues")
    for i in issues[:6]:
        print(f"    • {i}")

    # Render preview PNGs alongside the .sla / .pdf so the repo always
    # carries up-to-date previews of every page.
    import base64

    print("\n=== Render previews ===")
    for pn in range(1, TOTAL_PAGES + 1):
        out = await mcp.call_tool(
            "render_page_to_image",
            {"page_number": pn, "dpi": 110, "mode": MODE},
        )
        content = out[0] if isinstance(out, tuple) else out
        if isinstance(content, list):
            for c in content:
                if getattr(c, "type", None) == "image":
                    data = base64.b64decode(getattr(c, "data", ""))
                    fn = f"C:/Users/William/scribus-mcp/explainer-p{pn}.png"
                    with open(fn, "wb") as f:
                        f.write(data)
                    print(f"  page {pn}: wrote {fn} ({len(data)} bytes)")

    print(f"\nDone:\n  SLA: {SLA}\n  PDF: {PDF}")


asyncio.run(main())

# scribus-mcp — best practices for driving the tool surface

This is the "house style" for an LLM composing Scribus documents through
the MCP. Follow these rules and the result will read like a designed
deliverable, not a wall of frames.

The same content is exposed as the `best_practices` MCP prompt — when an
agent driving the MCP fetches that prompt, it gets this file verbatim.

## Composition: prefer patterns and layouts over primitives

The MCP exposes both raw primitives (`create_text_frame`, `create_rectangle`)
and composed patterns / layouts (`create_kpi_row`, `create_card_grid`,
`create_callout_box`, `create_radar_chart`, etc.). **Always reach for the
highest-level tool that fits the shape of your content.** Examples:

- 4 stat tiles in a row → `create_kpi_row` (handles widths, gaps, font
  auto-shrink). Don't loop over `create_kpi_tile`.
- 6 feature cards in a 2×3 grid → `create_card_grid`.
- A dashboard chart → `create_bar_chart` / `create_pie_chart` /
  `create_radar_chart` (all return a `bbox` dict you can chain).
- Highlighted code → `create_code_sample` (Pygments-tokenized, monospace
  auto-pick). Don't roll your own with `create_text_frame`.
- A bordered "tip / note / sidebar" block → `create_callout_box`.
- Markdown content → `import_markdown`, never hand-roll headings + bullet
  lists with primitives.
- Anchored stage list → `create_numbered_steps`.

Primitives are for composition glue (decorative shapes, page chrome,
filling gaps the patterns don't cover yet).

## Coordinates are millimetres, top-left origin

Every `_mm` parameter is millimetres. `x_mm` / `y_mm` is the **top-left**
of a bbox unless the parameter is explicitly named `center_*` (pie chart,
radar chart, dot label) or `axis_y_mm` / `top_y_mm` (timeline). For
charts that take a center, every slot returned by `PageCursor.split` /
`PageCursor.band` carries `center_x` / `center_y` precomputed — splat
them.

## Vertical flow: use PageCursor for multi-band scripts

```python
from scribus_mcp.layout import PageCursor

pc = PageCursor(x_mm=12, y_mm=22, width_mm=186, default_gap_mm=4)

await t("create_kpi_row", **pc.band(height_mm=38), items=[...])
left, right = pc.split([85, 101], height_mm=45)
await t("create_bar_chart", **left, ...)
await t("create_pie_chart", center_x_mm=right["center_x"], ...)
```

Hand-coding y values per band is the #1 source of overlap bugs. Let the
cursor do the math.

## Patterns return accurate bboxes

`create_bar_chart`, `create_radar_chart`, `create_timeline` all return
`bbox` in their result — that's the **true** total footprint (including
labels, legend, axis halo). Use it to advance `PageCursor` when in
doubt:

```python
r = await t("create_bar_chart", **pc.band(height_mm=50), values=[...])
# pc has already advanced past 50 mm — but if the chart actually drew
# something taller (e.g. a multi-dataset legend pushed the bbox down),
# correct with:
pc.jump_to(r["bbox"]["y_mm"] + r["bbox"]["height_mm"] + pc.default_gap_mm)
```

## Charts: `height_mm` is inclusive

`create_bar_chart.height_mm` is the **total** vertical footprint —
bars + gridlines + bottom category-label strip + legend strip (if
multi-dataset) + value-label strip (if `show_values`). Pass the slot's
full height; don't subtract a manual buffer.

For radar / pie, the chart sits at `(center_*, radius_*)` — labels poke
beyond the rings by `label_offset_mm + label_width_mm/2`. The defaults
(4 + 11 = 15 mm halo on radar) keep the chart tight enough to fit a
half-width column. Returned `bbox` is the truth.

## Compare variants → multi-dataset radar / bar

Pass `datasets=[{label, values, fill_color, …}, ...]` instead of a flat
`values=[...]`. The chart auto-renders a legend below (set
`legend_position="below"`) and overlapping radar polygons get partial
transparency (`fill_alpha=0.5`) so both stay legible.

## Colors must be defined before use

Every Scribus color reference (in any tool's `color`, `fill_color`,
`bar_color` etc.) must be a name **already defined in the document**. The
default palette is just `Black` / `White` plus a CMYK rotation. Define a
brand palette early:

```python
for n, c, m, y, k in (("Brand Deep", 85, 55, 0, 10), ...):
    await t("define_color_cmyk", name=n, cyan=c, magenta=m, yellow=y, key=k)
```

`create_code_sample` is the exception — it auto-defines token colors
from the Pygments style.

## Markdown handles inline emphasis automatically

`import_markdown` walks inline tokens, strips `**` / `*` / `` ` ``
markers, and re-applies bold / italic / monospace via `selectText` +
`setFont` (auto-discovers the bold/italic/mono variant of the frame's
font family). Don't pre-process markdown yourself — feed the raw source.

## Verify before declaring done

After building, **always**:

1. `preflight_check` — surface text overflow, missing images / fonts.
2. `render_page_to_image` for each page — eyeball the layout. Adjust if
   anything overlaps or sits in the page margin.
3. Only then `export_pdf`.

## Page chrome → master page or a `page_chrome()` helper

Header band, footer, accent rule — these repeat per page. Either build
them on a master page (`create_master_page` + `apply_master_page`) or
write a small `async def page_chrome(t, page_num, ...)` and call it once
per page (the demos use the latter).

## Custom fonts

Scribus only scans fonts at startup. Use `install_custom_font(font_path)`
to copy the file into a managed dir AND patch Scribus's *Additional Font
Paths* prefs — the font becomes available **after the next Scribus
launch**, not in the current session.

## Forms

`create_pdf_text_field` / `create_pdf_checkbox` / `create_pdf_combo_box`
etc. are the form-field tools. `create_link_annotation` /
`create_uri_annotation` / `create_text_annotation` cover navigation +
sticky-note annotations. Pass `target_x_mm` / `target_y_mm` (page coords
the link jumps to) and `frame_x_mm` / `frame_y_mm` / `frame_width_mm` /
`frame_height_mm` (where the clickable rectangle sits on the *current*
page).

## Pass plain text — never HTML-escape

Scribus's `setText` takes raw strings. If you pre-encode `&` as `&amp;` (or `<` as `&lt;`, etc.) the way you would for HTML, the encoded form ends up rendered literally in the PDF — Scribus stores user content as XML in the SLA file and re-escapes on save, so a pre-encoded `&amp;` becomes `&amp;amp;` on disk and renders as the five characters `&amp;`.

The MCP defends against this by running `html.unescape` on user-text inputs at the boundary (see `clean_user_text` in `src/scribus_mcp/tools/_common.py`), but you should still pass plain text:

| Don't | Do |
|---|---|
| `"R&amp;D"` | `"R&D"` |
| `"AT&amp;T merger"` | `"AT&T merger"` |
| `"foo &lt;bar&gt;"` | `"foo <bar>"` |

This applies to every tool that accepts user-visible text — `set_text`, `append_text`, `import_markdown`, every pattern's `title` / `caption` / `label` / `body`, every layout's `title` / `eyebrow` / `subtitle` / `right_text`, form `default_value` / `label`, annotation `link_text`, etc. The one exception is `create_code_sample`'s code body — code may legitimately contain literal `&amp;` and is passed through verbatim.

**Typographic entities are preserved.** `&nbsp;` decodes to U+00A0 (a real non-breaking space, *not* a regular space) — Scribus respects it at line-break time, so use it intentionally to keep words glued together: `"Apache&nbsp;2.0"` won't wrap between "Apache" and "2.0". Same goes for `&mdash;` (—), `&ndash;` (–), `&hellip;` (…), `&copy;` (©), etc. — they're decoded to the actual Unicode character, not stripped.

## Version-gated tools

A small number of tools wrap Scripter calls that only exist on Scribus 1.7+. If you call one on 1.6 you get a structured `ok=false` payload like:

```json
{
  "ok": false,
  "error": "create_qr_code_block (...) requires Scribus 1.7.0+ (this Scribus reports 1.6.3). ...",
  "required_version": "1.7.0",
  "actual_version": "1.6.3"
}
```

Surface this verbatim to the user — `required_version` and `actual_version` are stable fields you can pattern-match on. Don't retry the same tool, and don't paper over with primitives unless the user asks. Currently only `create_qr_code_block` is gated; see [doc/SUPPORT.md](SUPPORT.md) for the matrix.

## When in doubt

- Read [doc/SUPPORT.md](SUPPORT.md) — every Scripter function with
  Yes / Partial / No / N/A status.
- Read [doc/COOKBOOK.md](COOKBOOK.md) — end-to-end recipes for
  one-pagers, manuals, dashboards, and reports.
- Inspect the live document with the resources `scribus://document/info`,
  `…/colors`, `…/fonts`, `…/missing-resources`.

"""Layout tools — region-shaped helpers that carve a page area into zones
and (often) fill them with sensible defaults.

Patterns vs Layouts:
  - patterns/  produce a *content-shaped* visual (chart, callout, badge).
  - layouts/   produce a *region-shaped* composition (columns, sections,
               numbered step lists, hero bands). They typically compose
               multiple primitives and/or patterns.

Each file exposes one tool plus a ``register(mcp, ctx)`` function. Add a
new layout by dropping a file here and calling its register() below.
"""

from scribus_mcp.tools.layouts import (
    card_grid,
    equal_columns,
    hero_band,
    image_caption,
    kpi_row,
    numbered_steps,
    section_header,
    sidebar_layout,
    table_of_contents,
    text_with_image,
    two_column_text,
)


def register(mcp, ctx) -> None:
    section_header.register(mcp, ctx)
    hero_band.register(mcp, ctx)
    equal_columns.register(mcp, ctx)
    two_column_text.register(mcp, ctx)
    text_with_image.register(mcp, ctx)
    numbered_steps.register(mcp, ctx)
    image_caption.register(mcp, ctx)
    table_of_contents.register(mcp, ctx)
    sidebar_layout.register(mcp, ctx)
    kpi_row.register(mcp, ctx)
    card_grid.register(mcp, ctx)

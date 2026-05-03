"""High-level pattern tools — one tool per file.

Each pattern composes Scribus primitives into a sensible result with a
single MCP call. Add a new pattern by dropping a file here that exposes
``register(mcp, ctx)``, then importing + calling it from below.
"""

from scribus_mcp.tools.patterns import (
    bar_chart,
    callout_box,
    code_sample,
    comparison_table,
    dot_label,
    kpi_tile,
    pie_chart,
    qr_code_block,
    radar_chart,
    timeline,
)


def register(mcp, ctx) -> None:
    radar_chart.register(mcp, ctx)
    bar_chart.register(mcp, ctx)
    pie_chart.register(mcp, ctx)
    timeline.register(mcp, ctx)
    callout_box.register(mcp, ctx)
    kpi_tile.register(mcp, ctx)
    comparison_table.register(mcp, ctx)
    qr_code_block.register(mcp, ctx)
    dot_label.register(mcp, ctx)
    code_sample.register(mcp, ctx)

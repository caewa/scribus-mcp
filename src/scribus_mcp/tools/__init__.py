"""Tool modules. Each module exposes a `register(mcp, ctx)` function that
attaches its tools to the FastMCP server."""

from scribus_mcp.tools import (
    colors,
    document,
    escape,
    export,
    fonts,
    forms,
    frames,
    images,
    layers,
    layouts,
    markdown,
    pages,
    patterns,
    search,
    shapes,
    styles,
    styling,
    text,
)


def register_all(mcp, ctx) -> None:
    document.register(mcp, ctx)
    pages.register(mcp, ctx)
    frames.register(mcp, ctx)
    shapes.register(mcp, ctx)
    text.register(mcp, ctx)
    fonts.register(mcp, ctx)
    styles.register(mcp, ctx)
    styling.register(mcp, ctx)
    colors.register(mcp, ctx)
    images.register(mcp, ctx)
    layers.register(mcp, ctx)
    search.register(mcp, ctx)
    export.register(mcp, ctx)
    markdown.register(mcp, ctx)
    patterns.register(mcp, ctx)
    layouts.register(mcp, ctx)
    forms.register(mcp, ctx)
    escape.register(mcp, ctx)

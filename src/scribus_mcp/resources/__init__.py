from scribus_mcp.resources import document_state


def register_all(mcp, ctx) -> None:
    document_state.register(mcp, ctx)

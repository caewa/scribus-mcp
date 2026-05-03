from scribus_mcp.prompts import workflows


def register_all(mcp, ctx) -> None:
    workflows.register(mcp, ctx)

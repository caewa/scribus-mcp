from __future__ import annotations

import argparse
import sys

from scribus_mcp.config import Config
from scribus_mcp.server import build_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scribus-mcp", description="Scribus MCP server")
    parser.add_argument(
        "--http",
        metavar="HOST:PORT",
        help="Run as Streamable HTTP server (e.g. ':8765' or '127.0.0.1:8765'). Default is stdio.",
    )
    parser.add_argument(
        "--scribus-bin",
        help="Override path to the Scribus executable (or set SCRIBUS_BIN env var).",
    )
    parser.add_argument(
        "--enable-run-script",
        action="store_true",
        help="Enable the run_script escape-hatch tool (DANGER: arbitrary code execution).",
    )
    parser.add_argument(
        "--print-bridge-path",
        action="store_true",
        help="Print the path to the bundled bridge .spy file and exit.",
    )
    args = parser.parse_args(argv)

    if args.print_bridge_path:
        from scribus_mcp.bridge import bridge_path

        print(bridge_path())
        return 0

    import os

    if args.scribus_bin:
        os.environ["SCRIBUS_BIN"] = args.scribus_bin
    if args.enable_run_script:
        os.environ["SCRIBUS_MCP_RUN_SCRIPT"] = "1"

    cfg = Config.from_env()
    mcp = build_server(cfg)

    if args.http:
        host, _, port_s = args.http.rpartition(":")
        host = host or "127.0.0.1"
        port = int(port_s) if port_s else 8765
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())

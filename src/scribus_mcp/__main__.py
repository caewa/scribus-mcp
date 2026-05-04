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
    parser.add_argument(
        "--fetch-appimage",
        action="store_true",
        help=(
            "Download the official Scribus AppImage to ~/Applications/ and "
            "exit. Linux only. Pulls ~140 MB. Override defaults via "
            "--appimage-url / --appimage-version / --appimage-sha256 / "
            "--appimage-install-dir or the matching SCRIBUS_MCP_APPIMAGE_* "
            "env vars."
        ),
    )
    parser.add_argument("--appimage-url", help="Override the AppImage download URL.")
    parser.add_argument(
        "--appimage-version",
        help="Override the version tag used in the installed filename.",
    )
    parser.add_argument(
        "--appimage-sha256",
        help="Pin a SHA256 to verify the downloaded AppImage against.",
    )
    parser.add_argument(
        "--appimage-install-dir",
        help="Install directory (default: ~/Applications/).",
    )
    args = parser.parse_args(argv)

    if args.print_bridge_path:
        from scribus_mcp.bridge import bridge_path

        print(bridge_path())
        return 0

    import os

    if args.fetch_appimage:
        from pathlib import Path

        from scribus_mcp.appimage import (
            DEFAULT_APPIMAGE_VERSION,
            AppImageError,
            fetch_appimage,
        )

        url = args.appimage_url or os.environ.get("SCRIBUS_MCP_APPIMAGE_URL")
        version = (
            args.appimage_version
            or os.environ.get("SCRIBUS_MCP_APPIMAGE_VERSION")
            or DEFAULT_APPIMAGE_VERSION
        )
        sha256 = args.appimage_sha256 or os.environ.get(
            "SCRIBUS_MCP_APPIMAGE_SHA256"
        )
        raw_dir = args.appimage_install_dir or os.environ.get(
            "SCRIBUS_MCP_APPIMAGE_INSTALL_DIR"
        )
        try:
            path = fetch_appimage(
                url=url,
                version=version,
                install_dir=Path(raw_dir) if raw_dir else None,
                expected_sha256=sha256,
                log_fn=lambda m: print(m, file=sys.stderr),
            )
        except AppImageError as exc:
            print(f"fetch-appimage failed: {exc}", file=sys.stderr)
            return 1
        print(path)
        return 0

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

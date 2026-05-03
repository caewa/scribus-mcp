from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from typing import Any

from scribus_mcp.backends.base import BackendError, ScribusBackend, ScribusResult
from scribus_mcp.config import Config, read_discovery


class InteractiveBackend(ScribusBackend):
    """TCP loopback client that talks to a bridge.spy running inside Scribus.

    Discovery: reads {host, port, token} from the discovery file the bridge
    writes on startup. No persistent connection — opens TCP, sends one
    JSON request, reads one JSON response, closes. The bridge serializes
    requests onto Scribus's Qt main thread.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    async def _try_relaunch(self) -> bool:
        """Attempt to auto-launch Scribus + bridge. Returns True on success.

        Lazy-imports the launcher to avoid a circular import at module load.
        """
        from scribus_mcp.backends._launcher import ensure_bridge_running

        ok, _reason = await ensure_bridge_running(self.config, self)
        return ok

    async def is_available(self) -> bool:
        info = read_discovery(self.config.discovery_file)
        if not info:
            return False
        host = info.get("host", "127.0.0.1")
        port = info.get("port")
        if not port:
            return False
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=0.5
            )
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return True
        except (TimeoutError, OSError):
            return False

    async def call(self, method: str, *args: Any, **kwargs: Any) -> ScribusResult:
        return await self._send(
            {"kind": "call", "method": method, "args": list(args), "kwargs": kwargs}
        )

    async def script(self, body: str, result_expr: str = "None") -> ScribusResult:
        return await self._send({"kind": "exec", "body": body, "result_expr": result_expr})

    async def _send(self, msg: dict) -> ScribusResult:
        info = read_discovery(self.config.discovery_file)
        if not info:
            if not await self._try_relaunch():
                raise BackendError(
                    "No interactive bridge is running (discovery file missing) "
                    "and auto-launch failed"
                )
            info = read_discovery(self.config.discovery_file)
            if not info:
                raise BackendError("Bridge launched but did not write discovery file")
        host = info.get("host", "127.0.0.1")
        port = info["port"]
        token = info["token"]

        msg["id"] = uuid.uuid4().hex
        msg["token"] = token
        wire = (json.dumps(msg) + "\n").encode("utf-8")

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
        except (TimeoutError, OSError) as exc:
            if await self._try_relaunch():
                info = read_discovery(self.config.discovery_file) or info
                host = info.get("host", "127.0.0.1")
                port = info["port"]
                token = info["token"]
                msg["token"] = token
                wire = (json.dumps(msg) + "\n").encode("utf-8")
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=2.0
                    )
                except (TimeoutError, OSError) as exc2:
                    raise BackendError(
                        f"Bridge auto-relaunched but still unreachable at "
                        f"{host}:{port}: {exc2}"
                    ) from exc2
            else:
                raise BackendError(
                    f"Cannot reach Scribus bridge at {host}:{port}: {exc}"
                ) from exc

        try:
            writer.write(wire)
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=120.0)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

        if not line:
            raise BackendError("Bridge closed connection without responding")

        try:
            payload = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise BackendError(f"Bridge returned non-JSON: {line!r}") from exc

        return ScribusResult(
            ok=bool(payload.get("ok")),
            value=payload.get("value"),
            error=payload.get("error"),
            traceback=payload.get("traceback"),
        )

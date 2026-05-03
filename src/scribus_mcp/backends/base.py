from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class BackendError(RuntimeError):
    """Raised when the Scribus backend fails. Surfaces as a tool execution error."""


@dataclass
class ScribusResult:
    ok: bool
    value: Any = None
    error: str | None = None
    traceback: str | None = None
    stdout: str | None = None
    stderr: str | None = None

    def unwrap(self) -> Any:
        if not self.ok:
            msg = self.error or "Scribus call failed"
            if self.traceback:
                msg = f"{msg}\n{self.traceback}"
            raise BackendError(msg)
        return self.value

    def unwrap_or(self, default: Any = None) -> Any:
        """Return value on success, default on failure. Doesn't raise.

        Use this in tool layers that need to construct a structured
        response dict even when the underlying Scripter call failed —
        the caller checks `result.ok` and includes `result.error`.
        """
        return self.value if self.ok else default

    def to_response(self, **extra: Any) -> dict:
        """Convert into the standard tool-response dict shape.

        On success: {"ok": True, "value": <value>, **extra}
        On failure: {"ok": False, "error": <error>, **extra}

        Use this from MCP tool functions instead of raising BackendError;
        per the MCP spec, tool execution errors should be returned in
        the result so the model can self-correct.
        """
        if self.ok:
            return {"ok": True, "value": self.value, **extra}
        return {"ok": False, "error": self.error, **extra}


class ScribusBackend(ABC):
    """Common surface across headless and interactive backends.

    `call(method, *args, **kwargs)` invokes a Scripter function by name.
    `script(body, result_expr=...)` runs an arbitrary Python body in Scribus
    and returns the value of `result_expr` (or None).
    `is_available()` reports whether this backend can serve a request right now.
    """

    @abstractmethod
    async def call(self, method: str, *args: Any, **kwargs: Any) -> ScribusResult: ...

    @abstractmethod
    async def script(self, body: str, result_expr: str = "None") -> ScribusResult: ...

    @abstractmethod
    async def is_available(self) -> bool: ...

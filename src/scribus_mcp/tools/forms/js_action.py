"""JavaScript action handlers for form fields.

Scribus exposes 10 events you can attach a script to. Use these to wire
calculate/format/validate logic, navigate on click, reset forms, etc.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

# Per setJSActionScript docs
JS_EVENTS = {
    "mouse_up": 0,
    "mouse_down": 1,
    "mouse_enter": 2,
    "mouse_exit": 3,
    "focus_in": 4,
    "focus_out": 5,
    "selection_change": 6,
    "field_format": 7,
    "field_validate": 8,
    "field_calculate": 9,
}


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def set_js_action(
        name: str,
        event: str,
        script: str,
        mode: Mode = "auto",
    ) -> dict:
        """Attach a JavaScript action to a form field's event.

        ``event`` ∈ {mouse_up, mouse_down, mouse_enter, mouse_exit,
        focus_in, focus_out, selection_change, field_format,
        field_validate, field_calculate}.

        ``script`` is the body of the JavaScript handler. Examples:
            mouse_up:    ``"this.print();"``
            mouse_up:    ``"this.resetForm();"``
            field_format: ``"event.value = util.printf('%.2f', event.value);"``

        The target field must already be a PDF annotation (created via the
        form-field tools).
        """
        if event not in JS_EVENTS:
            return {"ok": False, "error": f"event must be one of {sorted(JS_EVENTS)}"}
        backend = await get_backend(ctx, mode)
        r = await backend.call("setJSActionScript", JS_EVENTS[event], script, name)
        return {"ok": r.ok, "value": r.unwrap_or(), "error": r.error}

    @mcp.tool()
    async def get_js_action(
        name: str,
        event: str,
        mode: Mode = "auto",
    ) -> dict:
        """Read the JavaScript script attached to a field's event. Returns
        None if no script is set or the action type isn't JavaScript."""
        if event not in JS_EVENTS:
            return {"ok": False, "error": f"event must be one of {sorted(JS_EVENTS)}"}
        backend = await get_backend(ctx, mode)
        r = await backend.call("getJSActionScript", JS_EVENTS[event], name)
        return {"ok": r.ok, "script": r.unwrap_or(), "error": r.error}

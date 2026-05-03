from __future__ import annotations

HEADLESS_TEMPLATE = """\
# -*- coding: utf-8 -*-
import json, sys, traceback
try:
    import scribus
except ImportError:
    sys.stderr.write("scribus module not available - this script must be run via 'scribus -g -py'\\n")
    sys.exit(2)

_RESULT_PATH = {result_path!r}

def _to_jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {{k: _to_jsonable(x) for k, x in v.items()}}
    return repr(v)

_out = {{"ok": False}}
try:
{body_indented}
    _out = {{"ok": True, "value": _to_jsonable({result_expr})}}
except Exception as exc:
    _out = {{
        "ok": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }}
finally:
    try:
        with open(_RESULT_PATH, "w", encoding="utf-8") as _f:
            json.dump(_out, _f)
    except Exception:
        sys.stderr.write(traceback.format_exc())
        sys.exit(3)
"""


def render_headless_script(body: str, result_expr: str, result_path: str) -> str:
    indented = "\n".join("    " + line if line else "" for line in body.splitlines()) or "    pass"
    return HEADLESS_TEMPLATE.format(
        body_indented=indented,
        result_expr=result_expr,
        result_path=result_path,
    )


def py_call(method: str, *args, **kwargs) -> str:
    """Build a Python source line that calls scribus.<method>(...) safely."""
    parts = [repr(a) for a in args]
    parts.extend(f"{k}={v!r}" for k, v in kwargs.items())
    return f"scribus.{method}({', '.join(parts)})"

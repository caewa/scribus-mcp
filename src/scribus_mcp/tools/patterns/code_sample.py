"""Syntax-highlighted code block.

Tokenizes ``code`` with Pygments, defines one document color per unique
token color the chosen Pygments style produces, then lays the text into a
monospace text frame and applies the colors per range via ``selectText`` +
``setTextColor``.

The Pygments dependency lives only in this module — import is deferred to
``register`` so the rest of the server keeps working even if Pygments is
missing (the tool itself returns a structured error instead of crashing).

Single-script-body design: every ``defineColorRGB``, ``createRect``,
``createText``, ``setText``, ``setFont``, ``selectText`` + ``setTextColor``
runs in one ``backend.script()`` call. The monospace-font resolution
also happens inside Scribus (via ``getFontNames``) so the whole pattern
is one round-trip.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend
from scribus_mcp.tools.palette import resolve_color
from scribus_mcp.tools.patterns._grouping import group_created_objects


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    """Parse a 3- or 6-digit hex (with or without ``#``) into 0–255 ints."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _color_name(hex6: str) -> str:
    """Stable Scribus color name for a hex triplet, e.g. ``PygC_3D7B7B``."""
    return f"PygC_{hex6.upper()}"


_MONO_FONT_HINTS = (
    "DejaVu Sans Mono",
    "JetBrains Mono",
    "Source Code Pro",
    "Fira Mono",
    "Fira Code",
    "Cascadia Mono",
    "Cascadia Code",
    "Consolas",
    "Inconsolata",
    "Roboto Mono",
    "IBM Plex Mono",
    "Liberation Mono",
    "Ubuntu Mono",
    "Menlo",
    "Monaco",
    "Courier New",
    "Courier",
)

# Sentinel used as the "color" value on line-number atoms, so the
# recolouring loop can identify them by identity rather than by hex —
# avoids the edge case where a Pygments token's color happens to match
# our line-number grey and gets recoloured incorrectly.
_LINE_NUMBER_SENTINEL = "_LN_"


def _atoms_with_line_numbers(
    atoms: list[tuple[str, str | None]],
    show_line_numbers: bool,
    line_count: int,
) -> list[tuple[str, str | None]]:
    """Optionally prepend ``"  N | "`` to each line.

    Pygments returns atoms whose text may span multiple lines (e.g. a
    multi-line string literal). We re-emit them split on ``\\n`` so the
    line-number prefix can be injected at the start of every line in a
    single pass.

    Line-number atoms carry the ``_LINE_NUMBER_SENTINEL`` value as their
    "color" field — that's resolved to the actual color name in the
    recolour loop. Using a sentinel rather than a hex avoids the edge
    case where a Pygments token using the same grey gets mis-recoloured.
    """
    if not show_line_numbers:
        return atoms
    width = len(str(max(line_count, 1)))
    out: list[tuple[str, str | None]] = []
    line_no = 1
    out.append((f"{line_no:>{width}} | ", _LINE_NUMBER_SENTINEL))
    for text, color in atoms:
        if "\n" not in text:
            out.append((text, color))
            continue
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if part:
                out.append((part, color))
            if i < len(parts) - 1:
                out.append(("\n", color))
                line_no += 1
                out.append((f"{line_no:>{width}} | ", _LINE_NUMBER_SENTINEL))
    # If the source ends with a newline we just emitted a prefix for a
    # line that has no content. Drop it.
    if out and out[-1][0].endswith(" | ") and out[-1][1] == _LINE_NUMBER_SENTINEL:
        out.pop()
    return out


def register(mcp, ctx: ServerCtx) -> None:
    try:
        from pygments import lex as _pyg_lex  # noqa: F401
        from pygments.lexers import get_lexer_by_name as _get_lexer_by_name  # noqa: F401
        from pygments.lexers import guess_lexer as _guess_lexer  # noqa: F401
        from pygments.styles import get_style_by_name as _get_style_by_name  # noqa: F401
        from pygments.util import ClassNotFound as _ClassNotFound  # noqa: F401
    except ImportError:
        _PYGMENTS_OK = False
    else:
        _PYGMENTS_OK = True

    @mcp.tool()
    async def create_code_sample(
        code: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        language: str = "",
        font: str = "",
        font_size_pt: float = 8.5,
        line_spacing_pt: float = 0.0,
        style: str = "default",
        title: str = "",
        title_height_mm: float = 6.0,
        title_font_size_pt: float = 9.0,
        title_color: str = "ink",
        title_fill_color: str = "",
        show_line_numbers: bool = False,
        line_number_color: str = "",
        background_color: str = "",
        border_color: str = "muted",
        border_shade: int | None = None,
        border_width_pt: float = 0.4,
        padding_mm: float = 3.0,
        mode: Mode = "auto",
    ) -> dict:
        """Syntax-highlighted code block in a monospace font.

        Tokenizes ``code`` with Pygments and recolors each token range with
        ``selectText`` + ``setTextColor``. Defines one Scribus color per
        unique token color produced by the chosen Pygments style.

        Layout
        ------
        - ``language`` is a Pygments lexer alias (``"python"``, ``"json"``,
          ``"bash"``, ``"javascript"``, ...). Empty string → auto-detect.
        - ``font`` empty → query Scribus's loaded fonts and pick a known
          monospace family. If none is recognized, falls back to the first
          font name containing "mono" or "courier"; otherwise the first
          font available. If no font is available at all the call fails.
        - ``style`` is any Pygments style name: ``"default"``, ``"monokai"``,
          ``"friendly"``, ``"github-dark"``, ``"vs"``, ``"emacs"``, etc.
        - ``title`` empty → no title bar. Otherwise a ``title_height_mm``
          strip is reserved at the top with the title in ``title_color``.
        - ``background_color`` empty → derive from the Pygments style's
          default background (defines a Scribus color for it). Pass an
          explicit Scribus color name to override.
        - ``line_spacing_pt`` 0 → auto (``font_size_pt * 1.25``).

        Returns the names of all created objects so the caller can re-style
        afterwards: ``{"background", "title_bar", "title_text", "code"}``.
        """
        if not _PYGMENTS_OK:
            return {
                "ok": False,
                "error": "Pygments is not installed. `pip install pygments`.",
            }

        from pygments import lex as pyg_lex
        from pygments.lexers import get_lexer_by_name, guess_lexer
        from pygments.styles import get_style_by_name
        from pygments.util import ClassNotFound

        # ---- 1. lexer + style ------------------------------------------------
        try:
            pyg_style = get_style_by_name(style)
        except ClassNotFound:
            return {"ok": False, "error": f"unknown pygments style: {style!r}"}

        try:
            lexer = get_lexer_by_name(language, stripnl=False) if language else guess_lexer(code)
        except ClassNotFound:
            return {"ok": False, "error": f"unknown pygments lexer: {language!r}"}

        # ---- 2. tokenize ----------------------------------------------------
        atoms: list[tuple[str, str | None]] = []
        for tok, val in pyg_lex(code, lexer):
            if not val:
                continue
            tok_style = pyg_style.style_for_token(tok)
            color = tok_style.get("color") or None
            atoms.append((val, color))

        line_count = code.count("\n") + (0 if code.endswith("\n") else 1)
        # If the code ends with \n, Pygments may produce an empty final line
        # — that's fine, we just don't add a number for it.

        # ---- 3. line-number column (optional) -------------------------------
        # Pygments doesn't expose a Token.LineNumbers across styles, so we
        # pick a sensible mid-grey based on the style's background
        # luminance — light theme → dark grey numbers, dark theme → light
        # grey numbers. Avoids white-on-white on Monokai etc.
        bg_hex_for_ln = (pyg_style.background_color or "#FFFFFF").lstrip("#") or "FFFFFF"
        if len(bg_hex_for_ln) == 3:
            bg_hex_for_ln = "".join(c * 2 for c in bg_hex_for_ln)
        try:
            r, g, b = (int(bg_hex_for_ln[i : i + 2], 16) for i in (0, 2, 4))
            # Rec. 709 luma
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        except ValueError:
            luma = 255
        ln_hex = "555555" if luma > 128 else "AAAAAA"
        atoms = _atoms_with_line_numbers(atoms, show_line_numbers, line_count)

        # Resolve the line-number color: caller-supplied name takes
        # precedence; otherwise we register the luma-aware grey above
        # as a Scribus color and use that.
        line_color_name = (
            line_number_color
            if (show_line_numbers and line_number_color)
            else _color_name(ln_hex.upper())
        )

        # ---- 4. Pre-compute primitive specs Python-side --------------------

        bg_hex = (pyg_style.background_color or "#FFFFFF").lstrip("#") or "FFFFFF"
        # Collect all unique token hex colors we need to register, plus
        # the background, plus the line-number grey (always — even if
        # show_line_numbers is False, registering it is cheap and
        # idempotent).
        unique_hex: set[str] = {bg_hex.upper(), ln_hex.upper()}
        for _, c in atoms:
            if c and c != _LINE_NUMBER_SENTINEL:
                unique_hex.add(c.upper())
        color_defs = []  # list of (color_name, r, g, b)
        for hex6 in sorted(unique_hex):
            r, g, b = _hex_to_rgb(hex6)
            color_defs.append((_color_name(hex6), r, g, b))

        bg_color_name = background_color or _color_name(bg_hex.upper())

        # Layout
        if title:
            if title_height_mm <= 0 or title_height_mm >= height_mm:
                return {
                    "ok": False,
                    "error": "title_height_mm must be > 0 and < height_mm",
                }
            code_y = y_mm + title_height_mm
            code_h = height_mm - title_height_mm
        else:
            code_y = y_mm
            code_h = height_mm

        code_frame_x = x_mm + padding_mm
        code_frame_y = code_y + padding_mm
        code_frame_w = width_mm - 2 * padding_mm
        code_frame_h = code_h - 2 * padding_mm
        if code_frame_w <= 0 or code_frame_h <= 0:
            return {"ok": False, "error": "padding_mm too large for given width/height"}

        # Per-range color application: group consecutive atoms with the
        # same color into one selectText call. Line-number atoms carry
        # the _LINE_NUMBER_SENTINEL string instead of a hex (set in
        # _atoms_with_line_numbers) so we can identify them by identity
        # — never by hex value, which could collide with a real token.
        full_text = "".join(text for text, _ in atoms)
        runs: list[tuple[int, int, str]] = []  # (cursor, length, color_name)
        cursor = 0
        i = 0
        n = len(atoms)
        while i < n:
            text, color = atoms[i]
            run_len = len(text)
            j = i + 1
            while j < n and atoms[j][1] == color:
                run_len += len(atoms[j][0])
                j += 1
            if color == _LINE_NUMBER_SENTINEL:
                runs.append((cursor, run_len, line_color_name))
            elif color:
                runs.append((cursor, run_len, _color_name(color.upper())))
            cursor += run_len
            i = j

        ls = float(line_spacing_pt) if line_spacing_pt > 0 else float(font_size_pt) * 1.25

        backend = await get_backend(ctx, mode)
        title_color, _ = await resolve_color(backend, title_color)
        border_color, border_shade = await resolve_color(
            backend, border_color, fallback_shade=25, current_shade=border_shade,
        )

        # ---- 5. One script body that creates everything -------------------
        # Includes monospace-font resolution inside Scribus so the whole
        # pattern is one round-trip.
        body = f"""
import scribus as _s

# Define every Pygments token color (idempotent if already exists).
for _name, _r, _g, _b in {color_defs!r}:
    try:
        _s.defineColorRGB(_name, _r, _g, _b)
    except Exception:
        pass  # color may already exist

# Resolve a monospace font, preferring well-known families.
_requested_font = {font!r}
_resolved_font = ""
if _requested_font:
    _resolved_font = _requested_font
else:
    try:
        _names = list(_s.getFontNames() or [])
    except Exception:
        _names = []
    _hints = {list(_MONO_FONT_HINTS)!r}
    for _fam in _hints:
        _fam_lo = _fam.lower()
        for _cand in _names:
            _lo = _cand.lower()
            if not _lo.startswith(_fam_lo):
                continue
            _tail = _cand[len(_fam):].strip().lower()
            if _tail in ("", "regular", "roman", "book"):
                _resolved_font = _cand
                break
        if _resolved_font:
            break
    if not _resolved_font:
        for _cand in _names:
            if "mono" in _cand.lower() or "courier" in _cand.lower():
                _resolved_font = _cand
                break
    if not _resolved_font and _names:
        _resolved_font = _names[0]

# Background rectangle (covers the code region).
_bg = _s.createRect({x_mm}, {code_y}, {width_mm}, {code_h})
_s.setFillColor({bg_color_name!r}, _bg)
"""
        if border_color and border_color != "None":
            body += (
                f"_s.setLineColor({border_color!r}, _bg)\n"
                f"_s.setLineShade({int(border_shade)}, _bg)\n"
                f"_s.setLineWidth({float(border_width_pt)}, _bg)\n"
            )
        else:
            body += '_s.setLineColor("None", _bg)\n'

        # Title bar (optional)
        if title:
            tfill = title_fill_color or bg_color_name
            body += f"""
_title_bar = _s.createRect({x_mm}, {y_mm}, {width_mm}, {title_height_mm})
_s.setFillColor({tfill!r}, _title_bar)
"""
            if border_color and border_color != "None":
                body += (
                    f"_s.setLineColor({border_color!r}, _title_bar)\n"
                    f"_s.setLineShade({int(border_shade)}, _title_bar)\n"
                    f"_s.setLineWidth({float(border_width_pt)}, _title_bar)\n"
                )
            else:
                body += '_s.setLineColor("None", _title_bar)\n'
            body += f"""
_title_text = _s.createText({x_mm + padding_mm}, {y_mm}, {width_mm - 2 * padding_mm}, {title_height_mm})
_s.setText({title!r}, _title_text)
_s.setFontSize({float(title_font_size_pt)}, _title_text)
_s.setTextColor({title_color!r}, _title_text)
_s.setTextVerticalAlignment(1, _title_text)
"""
        else:
            body += "_title_bar = None\n_title_text = None\n"

        # Code frame + text + per-range colors
        body += f"""
_code = _s.createText({code_frame_x}, {code_frame_y}, {code_frame_w}, {code_frame_h})
_s.setText({full_text!r}, _code)
if _resolved_font:
    _s.setFont(_resolved_font, _code)
_s.setFontSize({float(font_size_pt)}, _code)
_s.setLineSpacing({ls}, _code)
_s.setTextColor("Black", _code)
for _cur, _ln, _cname in {runs!r}:
    _s.selectText(_cur, _ln, _code)
    _s.setTextColor(_cname, _code)

_value = {{
    "background": _bg,
    "title_bar": _title_bar,
    "title_text": _title_text,
    "code": _code,
    "font": _resolved_font,
}}
"""

        res = await backend.script(body, result_expr="_value")
        if not res.ok:
            return {"ok": False, "error": res.error or "code_sample script failed"}

        out = res.value or {}
        if not out.get("font"):
            return {
                "ok": False,
                "error": "no fonts available in Scribus session",
                "background": out.get("background"),
                "title_bar": out.get("title_bar"),
                "title_text": out.get("title_text"),
                "code": out.get("code"),
            }
        group_name = await group_created_objects(
            backend,
            [
                out.get("background"),
                out.get("title_bar"),
                out.get("title_text"),
                out.get("code"),
            ],
        )
        return {
            "ok": True,
            "background": out.get("background"),
            "title_bar": out.get("title_bar"),
            "title_text": out.get("title_text"),
            "code": out.get("code"),
            "group": group_name,
            "language": getattr(lexer, "name", language or ""),
            "font": out.get("font"),
            "line_count": line_count,
            "color_count": len(unique_hex),
            "error": None,
        }

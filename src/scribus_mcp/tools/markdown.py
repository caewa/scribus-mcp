from __future__ import annotations

from dataclasses import dataclass, field

from markdown_it import MarkdownIt

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend


@dataclass
class Block:
    kind: str  # "heading" | "paragraph" | "code" | "list_item" | "image"
    level: int = 0
    text: str = ""
    src: str = ""  # for images
    items: list[str] = field(default_factory=list)
    # Inline emphasis ranges produced by ``_render_inline``: each entry is
    # ``(start, length, kind)`` where kind is "strong" | "em" | "code" — so
    # the layout body can apply per-range styling (bold / italic / mono)
    # via ``selectText`` + ``setFont``.
    runs: list[tuple[int, int, str]] = field(default_factory=list)
    # For list_item blocks, parallel arrays of items/items_runs.
    items_runs: list[list[tuple[int, int, str]]] = field(default_factory=list)


def _render_inline(children) -> tuple[str, list[tuple[int, int, str]]]:
    """Walk an inline token's children, return ``(clean_text, runs)``.

    ``clean_text`` is the visible text with all markdown markers (``**``,
    ``*``, ``` ` ```) stripped. ``runs`` is a list of
    ``(start, length, kind)`` tuples — one per emphasis span — that the
    layout body can re-apply via ``selectText`` + ``setFont``.
    """
    out: list[str] = []
    runs: list[tuple[int, int, str]] = []
    stack: list[tuple[str, int]] = []  # (kind, start_offset)
    cursor = 0

    for c in children or []:
        t = c.type
        if t == "text":
            out.append(c.content)
            cursor += len(c.content)
        elif t == "softbreak" or t == "hardbreak":
            out.append("\n" if t == "hardbreak" else " ")
            cursor += 1
        elif t == "code_inline":
            start = cursor
            out.append(c.content)
            cursor += len(c.content)
            runs.append((start, len(c.content), "code"))
        elif t == "strong_open":
            stack.append(("strong", cursor))
        elif t == "strong_close":
            if stack:
                kind, start = stack.pop()
                length = cursor - start
                if length > 0:
                    runs.append((start, length, kind))
        elif t == "em_open":
            stack.append(("em", cursor))
        elif t == "em_close":
            if stack:
                kind, start = stack.pop()
                length = cursor - start
                if length > 0:
                    runs.append((start, length, kind))
        elif t == "link_open":
            # Render link text inline, drop the URL — the visible page
            # only carries the anchor label.
            pass
        elif t == "link_close":
            pass
        elif t == "image":
            # Inline image inside a paragraph: emit the alt text.
            alt = c.content or ""
            out.append(alt)
            cursor += len(alt)
        # Anything else (mdash, etc.) is ignored at this level.
    return "".join(out), runs


def _parse_markdown(md: str) -> list[Block]:
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(md)
    blocks: list[Block] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            inline = tokens[i + 1]
            text, runs = _render_inline(inline.children)
            blocks.append(Block(kind="heading", level=level, text=text, runs=runs))
            i += 3
            continue
        if tok.type == "paragraph_open":
            inline = tokens[i + 1]
            children = inline.children or []
            # Detect a paragraph that is just a single image
            if len(children) == 1 and children[0].type == "image":
                src = children[0].attrs.get("src", "")
                blocks.append(Block(kind="image", src=src, text=children[0].content))
            else:
                text, runs = _render_inline(children)
                blocks.append(Block(kind="paragraph", text=text, runs=runs))
            i += 3
            continue
        if tok.type == "fence":
            blocks.append(Block(kind="code", text=tok.content))
            i += 1
            continue
        if tok.type == "bullet_list_open":
            items: list[str] = []
            items_runs: list[list[tuple[int, int, str]]] = []
            j = i + 1
            while j < len(tokens) and tokens[j].type != "bullet_list_close":
                if tokens[j].type == "inline":
                    text, runs = _render_inline(tokens[j].children)
                    items.append(text)
                    items_runs.append(runs)
                j += 1
            blocks.append(Block(kind="list_item", items=items, items_runs=items_runs))
            i = j + 1
            continue
        i += 1
    return blocks


_LAYOUT_BODY_TEMPLATE = """\
import scribus as _s

_blocks = {blocks!r}
_style_map = {style_map!r}
_x_mm = {x_mm}
_y_mm = {y_mm}
_w_mm = {w_mm}
_gap = 2.0  # vertical breathing room between blocks
_paginate = {paginate}

_created = []
_pos_y = _y_mm
_page_added = 0

# Page-bottom margin for auto-pagination. Pulled from the doc once
# (with a defensive fallback) — every block before drawing checks
# whether _pos_y + _h would cross _page_bottom and, if so, adds a
# page and resets _pos_y to _y_mm on the new page.
try:
    _page_w_mm, _page_h_mm = _s.getPageSize()
except Exception:
    _page_w_mm, _page_h_mm = (210.0, 297.0)
try:
    _margins = _s.getPageMargins()
    # margins shape: (top, left, right, bottom) in current unit
    _bottom_margin_mm = float(_margins[3]) if len(_margins) >= 4 else 12.0
except Exception:
    _bottom_margin_mm = 12.0
_page_bottom = _page_h_mm - _bottom_margin_mm

def _maybe_paginate(_h):
    global _pos_y, _page_added
    if not _paginate:
        return
    if _pos_y + _h <= _page_bottom:
        return
    try:
        _s.newPage(-1)  # -1 = append after last page
        _s.gotoPage(_s.pageCount())
        _pos_y = _y_mm
        _page_added += 1
    except Exception:
        pass  # if newPage fails, fall through and let the block overflow

def _new_text(_h):
    _name = _s.createText(_x_mm, _pos_y, _w_mm, _h)
    return _name

# --- Height estimation --------------------------------------------------
# Two-step approach (mirrors the create_numbered_badge pattern):
#   1. Use the cheap ``_estimate_block_height`` heuristic to pick a
#      starting height — keeps the typical case to one frame creation.
#   2. After ``setText`` + ``layoutText``, ``_fit_height`` grows the
#      frame if the text overflows, then shrinks it 1 mm at a time
#      until just before overflow. Returns the actual just-fits height
#      so the cursor advances by the *real* footprint, not the
#      estimate. This kills the "lot of space" gaps between blocks
#      that the pure-heuristic version produced.

def _wrapped_lines(_text, _line_w_mm, _avg_char_mm):
    # Each manual newline starts a new line; within a line, we estimate
    # how many wrapped sub-lines the text would occupy at the given
    # average character width.
    if not _text:
        return 1
    _chars_per_line = max(1, int(_line_w_mm / _avg_char_mm))
    _total = 0
    for _ln in _text.split('\\n'):
        if not _ln:
            _total += 1
            continue
        _total += max(1, (len(_ln) + _chars_per_line - 1) // _chars_per_line)
    return max(1, _total)

def _estimate_block_height(_block):
    _kind = _block['kind']
    if _kind == 'heading':
        # Heading sizes shrink with level (h1 biggest); ~1.5x body line
        # height per line of heading text.
        _level = _block.get('level', 1)
        _font_pt = max(11, 22 - 2 * _level)
        _line_h_mm = (_font_pt / 72) * 25.4 * 1.3
        _avg_char_mm = (_font_pt / 72) * 25.4 * 0.5
        _lines = _wrapped_lines(_block.get('text', ''), _w_mm, _avg_char_mm)
        return max(8.0, _lines * _line_h_mm + 1.0)
    if _kind == 'paragraph':
        # Body ~ 11 pt with 1.25 leading -> ~ 4.85 mm per line.
        _line_h_mm = 5.0
        _avg_char_mm = 2.0  # proportional font, conservative
        _lines = _wrapped_lines(_block.get('text', ''), _w_mm, _avg_char_mm)
        return max(6.0, _lines * _line_h_mm + 1.5)
    if _kind == 'code':
        # Monospace: ~ 9 pt with tight leading -> ~ 4 mm per line.
        _line_h_mm = 4.2
        _avg_char_mm = 1.8
        _lines = _wrapped_lines(_block.get('text', ''), _w_mm - 4, _avg_char_mm)
        return max(6.0, _lines * _line_h_mm + 3.0)
    if _kind == 'list_item':
        # One bullet line per item, plus wrap for long bullet text.
        _line_h_mm = 5.0
        _avg_char_mm = 2.0
        _items = _block.get('items', []) or []
        _total = 0
        for _it in _items:
            _total += _wrapped_lines('• ' + (_it or ''), _w_mm, _avg_char_mm)
        return max(6.0, _total * _line_h_mm + 1.5)
    if _kind == 'image':
        return 60.0
    return 12.0

def _fit_height(_name, _initial_h, _min_h=4.0, _max_h=300.0,
                _grow_step=6.0, _shrink_step=1.0,
                _max_grow_iter=20, _max_shrink_iter=30):
    # Two-step measure-and-resize. Caller has already filled the frame
    # with text + styling; we just probe ``textOverflows`` to find the
    # smallest height that doesn't truncate the text, then resize the
    # frame to that height.
    _h = _initial_h
    try:
        _s.layoutText(_name)
    except Exception:
        return _h
    # Grow until the text fits.
    _i = 0
    while _i < _max_grow_iter:
        try:
            _overflow = bool(_s.textOverflows(_name))
        except Exception:
            return _h
        if not _overflow:
            break
        _h = min(_max_h, _h + _grow_step)
        try:
            _s.sizeObject(_w_mm, _h, _name)
            _s.layoutText(_name)
        except Exception:
            return _h
        if _h >= _max_h:
            break
        _i += 1
    # Shrink until just before overflow. Track the last known-good
    # height in case the next shrink step pushes us into overflow.
    _last_good = _h
    _i = 0
    while _i < _max_shrink_iter:
        _new_h = _h - _shrink_step
        if _new_h < _min_h:
            break
        try:
            _s.sizeObject(_w_mm, _new_h, _name)
            _s.layoutText(_name)
            _overflow = bool(_s.textOverflows(_name))
        except Exception:
            break
        if _overflow:
            # Restore the last good height and stop.
            try:
                _s.sizeObject(_w_mm, _last_good, _name)
            except Exception:
                pass
            _h = _last_good
            break
        _last_good = _new_h
        _h = _new_h
        _i += 1
    return _h

# --- Inline-emphasis helpers ----------------------------------------------
# Per-call cache: lives only for the duration of one import_markdown
# script body. Within that single call we repeatedly look up "base font
# + style suffix" pairs (one per emphasis run), so memoising is worth
# it. The cache resets every call — no cross-call state.
_AVAIL_FONTS = set()
try:
    _AVAIL_FONTS = set(_s.getFontNames() or [])
except Exception:
    _AVAIL_FONTS = set()

_FONT_VARIANT_CACHE = {{}}

def _strip_suffix(_name):
    # Common Scribus suffixes appended to family names. Order matters —
    # check the longest first.
    for _suf in (
        ' Bold Italic', ' Bold Oblique', ' BoldItalic',
        ' Italic', ' Oblique',
        ' Bold', ' Heavy', ' Black',
        ' Regular', ' Roman', ' Book',
    ):
        if _name.endswith(_suf):
            return _name[:-len(_suf)]
    return _name

def _font_variant(_base_font, _kind):
    # Try to find a Bold / Italic / Mono variant of _base_font in the
    # available fonts. Returns the variant name or None if none exists.
    _key = (_base_font, _kind)
    if _key in _FONT_VARIANT_CACHE:
        return _FONT_VARIANT_CACHE[_key]
    _family = _strip_suffix(_base_font)
    _candidates = []
    if _kind == 'strong':
        _candidates = [_family + ' Bold', _family + ' Heavy', _family + ' Black']
    elif _kind == 'em':
        _candidates = [_family + ' Italic', _family + ' Oblique']
    elif _kind == 'code':
        # Look for a known mono face — full match against the family name.
        for _mono in ('DejaVu Sans Mono', 'Consolas', 'Courier New',
                      'Liberation Mono', 'Source Code Pro', 'Menlo',
                      'JetBrains Mono', 'Fira Mono'):
            for _suf in ('', ' Regular', ' Book', ' Roman'):
                _cand = (_mono + _suf).rstrip()
                if _cand in _AVAIL_FONTS:
                    _FONT_VARIANT_CACHE[_key] = _cand
                    return _cand
        _FONT_VARIANT_CACHE[_key] = None
        return None
    for _cand in _candidates:
        if _cand in _AVAIL_FONTS:
            _FONT_VARIANT_CACHE[_key] = _cand
            return _cand
    _FONT_VARIANT_CACHE[_key] = None
    return None

def _apply_runs(_name, _runs, _base_offset):
    if not _runs:
        return
    try:
        _base_font = _s.getFont(_name)
    except Exception:
        return
    for _start, _length, _kind in _runs:
        _variant = _font_variant(_base_font, _kind)
        if not _variant:
            continue
        try:
            _s.selectText(_start + _base_offset, _length, _name)
            _s.setFont(_variant, _name)
        except Exception:
            pass

# --- Block layout ----------------------------------------------------------

for _b in _blocks:
    _kind = _b['kind']
    _h = _estimate_block_height(_b)
    _maybe_paginate(_h)
    if _kind == 'heading':
        _name = _new_text(_h)
        _s.setText(_b['text'], _name)
        _style = _style_map.get('h%d' % _b['level'])
        if _style:
            try:
                _s.setParagraphStyle(_style, _name)
            except Exception:
                pass
        _apply_runs(_name, _b.get('runs') or [], 0)
        _h = _fit_height(_name, _h)
        _created.append({{'name': _name, 'kind': 'heading', 'level': _b['level']}})
        _pos_y += _h + _gap
    elif _kind == 'paragraph':
        _name = _new_text(_h)
        _s.setText(_b['text'], _name)
        _style = _style_map.get('body')
        if _style:
            try:
                _s.setParagraphStyle(_style, _name)
            except Exception:
                pass
        _apply_runs(_name, _b.get('runs') or [], 0)
        _h = _fit_height(_name, _h)
        _created.append({{'name': _name, 'kind': 'paragraph'}})
        _pos_y += _h + _gap
    elif _kind == 'code':
        _name = _new_text(_h)
        _s.setText(_b['text'], _name)
        _style = _style_map.get('code')
        if _style:
            try:
                _s.setParagraphStyle(_style, _name)
            except Exception:
                pass
        _h = _fit_height(_name, _h)
        _created.append({{'name': _name, 'kind': 'code'}})
        _pos_y += _h + _gap
    elif _kind == 'list_item':
        _items = _b['items']
        _items_runs = _b.get('items_runs') or [[] for _ in _items]
        _bullet_text = '\\n'.join(['• ' + _it for _it in _items])
        _name = _new_text(_h)
        _s.setText(_bullet_text, _name)
        _style = _style_map.get('list')
        if _style:
            try:
                _s.setParagraphStyle(_style, _name)
            except Exception:
                pass
        # Apply inline emphasis per list item — each item is prefixed by
        # "• " (2 chars) and joined by '\\n' (1 char).
        _line_off = 0
        for _it_text, _it_runs in zip(_items, _items_runs):
            _apply_runs(_name, _it_runs, _line_off + 2)
            _line_off += 2 + len(_it_text) + 1  # "• " + text + "\\n"
        _h = _fit_height(_name, _h)
        _created.append({{'name': _name, 'kind': 'list_item'}})
        _pos_y += _h + _gap
    elif _kind == 'image':
        _name = _s.createImage(_x_mm, _pos_y, _w_mm, _h)
        if _b.get('src'):
            try:
                _s.loadImage(_b['src'], _name)
                _s.setScaleImageToFrame(1, 1, _name)
            except Exception:
                pass
        _created.append({{'name': _name, 'kind': 'image', 'src': _b.get('src', '')}})
        _pos_y += _h + _gap

_value = {{'frames': _created, 'final_y_mm': _pos_y, 'pages_added': _page_added}}
"""


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def import_markdown(
        markdown_text: str,
        x_mm: float = 20.0,
        y_mm: float = 20.0,
        width_mm: float = 170.0,
        style_h1: str = "",
        style_h2: str = "",
        style_h3: str = "",
        style_body: str = "",
        style_code: str = "",
        style_list: str = "",
        paginate: bool = True,
        mode: Mode = "auto",
    ) -> dict:
        """Convert Markdown to a stack of Scribus frames.

        Each block (heading, paragraph, code, list, image) becomes a frame,
        stacked vertically starting at (x_mm, y_mm) with the given width.
        Provide style names to apply Scribus paragraph styles to each kind.

        ``paginate`` (default True): when a block would cross the page's
        bottom margin, append a new page and continue the stack from
        ``y_mm`` on it. The result's ``pages_added`` counts how many new
        pages were created. Set to False to keep the original
        single-page-stacks-off-the-bottom behaviour.
        """
        blocks = _parse_markdown(markdown_text)
        block_dicts = [
            {
                "kind": b.kind,
                "level": b.level,
                "text": b.text,
                "src": b.src,
                "items": b.items,
                "runs": b.runs,
                "items_runs": b.items_runs,
            }
            for b in blocks
        ]
        style_map = {
            "h1": style_h1,
            "h2": style_h2,
            "h3": style_h3,
            "body": style_body,
            "code": style_code,
            "list": style_list,
        }
        style_map = {k: v for k, v in style_map.items() if v}
        body = _LAYOUT_BODY_TEMPLATE.format(
            blocks=block_dicts,
            style_map=style_map,
            x_mm=x_mm,
            y_mm=y_mm,
            w_mm=width_mm,
            paginate=bool(paginate),
        )
        backend = await get_backend(ctx, mode)
        result = await backend.script(body, result_expr="_value")
        return {"ok": result.ok, "value": result.unwrap_or(), "error": result.error}

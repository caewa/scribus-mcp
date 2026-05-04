"""Reusable Scribus-side helpers for fitting frames to their content.

The header strings in this module are *script bodies* — text that the
MCP injects into a ``backend.script(...)`` call so it runs inside
Scribus's interpreter. They define helper functions on the Scribus
side that the calling tool's body can then invoke.

Why script-side instead of MCP-side? Sizing depends on Scribus's
text engine: width, font, leading, hyphenation, glyph metrics. The
only reliable way to know if text fits is to call ``layoutText`` and
``textOverflows``. Doing that round-trip per-mm-of-search would be
~50 round trips. Doing it inside one script body is one round trip.
"""

from __future__ import annotations

# ``_fit_text_frame`` shrinks a single Scribus text frame to its
# content. Caller has already done ``setText`` + any styling. We probe
# ``textOverflows`` to find the smallest height that doesn't truncate,
# resize via ``sizeObject``, and return the final height in mm.
#
# The grow phase handles the case where the caller passed an initial
# height that's too small (story would overflow); the shrink phase
# handles the case where the caller passed a generously tall frame
# and the story doesn't fill it.
FIT_TEXT_FRAME_HELPER = """
def _fit_text_frame(_name, _w_mm, _initial_h_mm,
                    _min_h_mm=4.0, _max_h_mm=400.0,
                    _grow_step=4.0, _shrink_step=1.0,
                    _max_grow=40, _max_shrink=80):
    import scribus as __s
    _h = _initial_h_mm
    try:
        __s.layoutText(_name)
    except Exception:
        return _h
    # Grow until the text fits.
    _i = 0
    while _i < _max_grow:
        try:
            _overflow = bool(__s.textOverflows(_name))
        except Exception:
            return _h
        if not _overflow:
            break
        _new_h = min(_max_h_mm, _h + _grow_step)
        if _new_h == _h:
            break
        _h = _new_h
        try:
            __s.sizeObject(_w_mm, _h, _name)
            __s.layoutText(_name)
        except Exception:
            return _h
        _i += 1
    # Shrink until just before overflow.
    _last_good = _h
    _i = 0
    while _i < _max_shrink:
        _new_h = _h - _shrink_step
        if _new_h < _min_h_mm:
            break
        try:
            __s.sizeObject(_w_mm, _new_h, _name)
            __s.layoutText(_name)
            _overflow = bool(__s.textOverflows(_name))
        except Exception:
            break
        if _overflow:
            try:
                __s.sizeObject(_w_mm, _last_good, _name)
            except Exception:
                pass
            _h = _last_good
            break
        _last_good = _new_h
        _h = _new_h
        _i += 1
    return _h
"""


__all__ = ["FIT_TEXT_FRAME_HELPER"]

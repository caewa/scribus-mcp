"""Unit tests for ``clean_user_text``.

Covers the LLM over-encoding scenarios we observed in the wild:
``"OVERVIEW &AMP; KERNEL FEATURES"`` and
``"Kernel &amp;amp; runtime features"`` came out of `setText` calls
where the LLM had pre-encoded ``&`` for HTML and Scribus then double-
escaped on save, producing literal ``&amp;`` in the rendered PDF.
"""

from __future__ import annotations

from scribus_mcp.tools._common import clean_user_text


def test_decodes_amp_entity():
    assert clean_user_text("AT&amp;T") == "AT&T"


def test_decodes_uppercase_amp_entity():
    # Real LLM regression: ``OVERVIEW &AMP; KERNEL FEATURES`` came out
    # because the LLM wrote ``&AMP;`` (uppercase) thinking it was
    # HTML-encoding for an uppercased eyebrow.
    assert clean_user_text("OVERVIEW &AMP; KERNEL FEATURES") == "OVERVIEW & KERNEL FEATURES"


def test_decodes_lt_gt():
    assert clean_user_text("foo &lt;bar&gt; baz") == "foo <bar> baz"


def test_decodes_numeric_entities():
    assert clean_user_text("&#x26;") == "&"
    assert clean_user_text("&#38;") == "&"


def test_single_pass_preserves_intentional_amp():
    # ``&amp;amp;`` is "I want a literal &amp; to render". One pass of
    # unescape collapses the outer entity, leaving ``&amp;``. That's
    # the LLM's intent if it actually wrote the inner entity.
    assert clean_user_text("Kernel &amp;amp; runtime") == "Kernel &amp; runtime"


def test_leaves_bare_ampersand_alone():
    assert clean_user_text("Ben & Jerry's") == "Ben & Jerry's"


def test_leaves_plain_text_alone():
    s = "The quick brown fox jumps over the lazy dog. 1234567890."
    assert clean_user_text(s) == s


def test_handles_empty():
    assert clean_user_text("") == ""


def test_handles_unicode():
    # Scribus DTP often gets em-dashes, accented chars, math symbols.
    s = "Hé—naïve 0–100 2×3 résumé"
    assert clean_user_text(s) == s


def test_decodes_nbsp_to_non_breaking_space():
    # ``&nbsp;`` is a typographic choice: keep words on the same line.
    # Decoding to U+00A0 (NOT a regular ASCII space) preserves that
    # intent — Scribus respects U+00A0 as a non-breaking space at
    # layout time, so e.g. "Apache 2.0" with ``&nbsp;`` between
    # "Apache" and "2.0" stays glued together. Critically: this is
    # NOT the same as ``" "`` (U+0020), which Scribus is free to
    # break across lines.
    out = clean_user_text("Apache&nbsp;2.0")
    assert out == "Apache 2.0"
    assert " " in out
    assert " " not in out  # explicit: no ASCII space introduced


def test_decodes_typographic_entities():
    # The other common LLM-helpful-encodings the MCP should silently
    # decode: em/en dashes, ellipsis, copyright, middle dot.
    cases = {
        "a &mdash; b": "a — b",
        "0 &ndash; 100": "0 – 100",
        "etc&hellip;": "etc…",
        "&copy; 2026": "© 2026",
        "a &middot; b": "a · b",
    }
    for src, expected in cases.items():
        assert clean_user_text(src) == expected

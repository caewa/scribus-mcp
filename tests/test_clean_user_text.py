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

"""Font management.

Scribus discovers fonts at startup from three sources:
  1. The OS's system font directories (registry on Windows, fontconfig on
     Linux, Font Book on macOS).
  2. Scribus's bundled fonts (shipped inside the application).
  3. Any "Additional Font Paths" the user has configured under
     File > Preferences > Fonts (stored in the prefs XML as
     ``<context name="Fonts"><table name="ExtraFontDirs">…</table></context>``).

Scripter exposes the *result* of that discovery (``getFontNames``,
``getXFontNames``) but does NOT let you load a new font into the running
session. To make a custom font available, the user must either install it
on the OS or add its directory to Scribus's additional-font-paths and
**restart Scribus**. This module covers both halves of that flow:

  - Read-only discovery: ``list_fonts`` / ``list_fonts_detailed`` /
    ``list_monospace_fonts`` / ``font_is_available`` /
    ``get_text_frame_font``.
  - Pre-launch staging: ``install_custom_font`` copies a font file into a
    managed directory and patches Scribus's prefs XML so the directory
    appears in *Additional Font Paths*. Takes effect on the next Scribus
    launch — never inside a running session, since Scribus only scans for
    fonts at startup.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

# Substrings that strongly suggest a font is monospaced. These are common
# across the major free + commercial monospace families. The match is
# case-insensitive and on the FAMILY portion of the name only — e.g.
# "Source Code Pro Bold Italic" -> family "Source Code Pro" matches
# "source code".
_MONO_HINTS = (
    "mono",  # *Mono, Mono*
    "courier",  # Courier, Courier New
    "consolas",  # Windows
    "menlo",  # macOS
    "monaco",  # macOS classic
    "source code",  # Source Code Pro
    "fira code",
    "fira mono",
    "jetbrains mono",
    "cascadia",  # Cascadia Code / Mono
    "inconsolata",
    "hack",
    "iosevka",
    "ubuntu mono",
    "dejavu sans mono",
    "liberation mono",
    "anonymous pro",
    "pt mono",
    "roboto mono",
    "noto sans mono",
    "noto mono",
    "ibm plex mono",
)


def _looks_monospace(family: str) -> bool:
    f = family.lower()
    return any(h in f for h in _MONO_HINTS)


# Recognized font file extensions. Scribus parses TTF, OTF, TTC, PFA, PFB.
_FONT_EXTS = {".ttf", ".otf", ".ttc", ".pfa", ".pfb"}


def _scribus_prefs_dir() -> Path | None:
    """Best-effort location of Scribus's per-user prefs directory.

    Returns the directory itself; the prefs XML is usually
    ``prefs17X.xml`` inside it (X varies with the point release). Returns
    ``None`` if no candidate exists — the caller should treat that as
    "Scribus has never run on this machine; tell the user to launch it
    once first".
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            cand = Path(appdata) / "Scribus"
            if cand.is_dir():
                return cand
    elif sys.platform == "darwin":
        cand = Path.home() / "Library" / "Preferences" / "Scribus"
        if cand.is_dir():
            return cand
    else:  # linux / *bsd
        xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        cand = Path(xdg) / "scribus"
        if cand.is_dir():
            return cand
        cand = Path.home() / ".scribus"
        if cand.is_dir():
            return cand
    return None


def _find_prefs_xml(prefs_dir: Path) -> Path | None:
    """Pick the most recent ``prefs17X.xml`` (or ``prefs15X.xml``) file in
    a Scribus prefs directory."""
    candidates: list[Path] = []
    for pat in ("prefs17*.xml", "prefs15*.xml", "prefs16*.xml"):
        candidates.extend(prefs_dir.glob(pat))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _font_dirs_table(root: ET.Element) -> ET.Element:
    """Find the ``<table name="ExtraFontDirs">`` element under
    ``application``, creating any missing ancestors. Returns the element."""
    # <preferences> -> <level name="application"> -> <context name="Fonts">
    #   -> <table name="ExtraFontDirs">
    level = None
    for el in root.findall("level"):
        if el.get("name") == "application":
            level = el
            break
    if level is None:
        level = ET.SubElement(root, "level", {"name": "application"})

    fonts_ctx = None
    for el in level.findall("context"):
        if el.get("name") == "Fonts":
            fonts_ctx = el
            break
    if fonts_ctx is None:
        fonts_ctx = ET.SubElement(level, "context", {"name": "Fonts"})

    table = None
    for el in fonts_ctx.findall("table"):
        if el.get("name") == "ExtraFontDirs":
            table = el
            break
    if table is None:
        table = ET.SubElement(fonts_ctx, "table", {"name": "ExtraFontDirs"})
    return table


def _read_extra_font_dirs(table: ET.Element) -> list[str]:
    """Read each ``<row><col>…</col></row>`` text inside the table."""
    out: list[str] = []
    for row in table.findall("row"):
        cols = row.findall("col")
        if cols and cols[0].text:
            out.append(cols[0].text)
    return out


def _add_extra_font_dir(table: ET.Element, directory: str) -> bool:
    """Insert directory as a new row, idempotently. Returns True if added,
    False if it was already present."""
    existing = _read_extra_font_dirs(table)
    norm = str(Path(directory).resolve())
    for e in existing:
        try:
            if str(Path(e).resolve()) == norm:
                return False
        except OSError:
            if e == directory:
                return False
    row = ET.SubElement(table, "row")
    col = ET.SubElement(row, "col")
    col.text = norm
    return True


def _backup_path(p: Path) -> Path:
    """Side-by-side ``.scribus-mcp.bak`` so the user can roll back."""
    return p.with_suffix(p.suffix + ".scribus-mcp.bak")


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def list_fonts(mode: Mode = "auto") -> dict:
        """All font face names Scribus knows about.

        Each entry is the full Scribus font key, including the style suffix
        (e.g. ``"DejaVu Sans Mono Bold"``). Pass any of these strings to
        ``set_font`` or to a pattern's ``font`` parameter.
        """
        backend = await get_backend(ctx, mode)
        r = await backend.call("getFontNames")
        return {"ok": r.ok, "fonts": r.unwrap_or([]), "error": r.error}

    @mcp.tool()
    async def list_fonts_detailed(mode: Mode = "auto") -> dict:
        """Rich font info from ``getXFontNames``.

        Returns a list of records, one per face. Each record has:
          - ``family``: family name (e.g. "DejaVu Sans Mono")
          - ``name``: full Scribus key (the same string as in
            ``list_fonts`` — pass this to ``set_font``)
          - ``filename``: path to the font file on disk
          - ``ps_name``: PostScript name
          - ``embeddable``: True if Scribus can embed/subset it in PDF
            export

        Useful when you need to filter by file path, PostScript name, or
        embedability.
        """
        backend = await get_backend(ctx, mode)
        r = await backend.call("getXFontNames")
        rows = r.unwrap_or([]) or []
        out: list[dict] = []
        for entry in rows:
            # Scripter returns 5-tuples: (family, name, filename, ps_name,
            # embed_flag). Be tolerant of shorter/longer rows.
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            family = entry[0] if len(entry) > 0 else ""
            name = entry[1] if len(entry) > 1 else ""
            filename = entry[2] if len(entry) > 2 else ""
            ps_name = entry[3] if len(entry) > 3 else ""
            embed = bool(entry[4]) if len(entry) > 4 else None
            out.append(
                {
                    "family": family,
                    "name": name,
                    "filename": filename,
                    "ps_name": ps_name,
                    "embeddable": embed,
                }
            )
        return {"ok": r.ok, "fonts": out, "error": r.error}

    @mcp.tool()
    async def list_monospace_fonts(mode: Mode = "auto") -> dict:
        """Subset of ``list_fonts`` filtered to monospace-looking families.

        Heuristic: matches family names against a list of well-known
        monospace identifiers (Courier, Consolas, DejaVu Sans Mono, Fira
        Code, JetBrains Mono, Source Code Pro, etc.). It's not exhaustive —
        if you've installed a custom mono that isn't in the hint list, it
        won't be picked up. In that case, use ``list_fonts`` and pick by
        name.

        Returns ``{"fonts": [...]}`` ordered alphabetically, with the
        recommended (preferred) face surfaced as ``"preferred"`` for
        convenience — typically the regular weight of the first widely-used
        family in the list.
        """
        backend = await get_backend(ctx, mode)
        r = await backend.call("getFontNames")
        names = r.unwrap_or([]) or []
        monos = sorted(n for n in names if _looks_monospace(n))
        # Prefer a "Regular"/"Roman"/no-style face from the most common
        # families if available — gives a sensible default for code blocks.
        preferred = None
        family_priority = (
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
        for fam in family_priority:
            for cand in monos:
                # Prefer a regular cut: the entry whose extra suffix is
                # empty, "Regular", "Roman", or "Book".
                lo = cand.lower()
                if not lo.startswith(fam.lower()):
                    continue
                tail = cand[len(fam) :].strip().lower()
                if tail in ("", "regular", "roman", "book"):
                    preferred = cand
                    break
            if preferred:
                break
        if preferred is None and monos:
            preferred = monos[0]
        return {
            "ok": r.ok,
            "fonts": monos,
            "preferred": preferred,
            "error": r.error,
        }

    @mcp.tool()
    async def get_text_frame_font(name: str, mode: Mode = "auto") -> dict:
        """Return the font currently set on a text frame.

        Mirrors ``getFont`` from the Scripter API. Returns ``None`` if the
        frame has no text or isn't a text frame.
        """
        backend = await get_backend(ctx, mode)
        r = await backend.call("getFont", name)
        return {"ok": r.ok, "font": r.unwrap_or(), "error": r.error}

    @mcp.tool()
    async def font_is_available(font: str, mode: Mode = "auto") -> dict:
        """True if ``font`` is in ``getFontNames`` exactly (case-sensitive).

        Use before applying a font to a frame, since ``setFont`` raises
        ``ValueError`` if the font isn't loaded — better to surface a
        graceful error and pick a fallback.
        """
        backend = await get_backend(ctx, mode)
        r = await backend.call("getFontNames")
        names = set(r.unwrap_or([]) or [])
        return {"ok": r.ok, "available": font in names, "error": r.error}

    @mcp.tool()
    async def list_extra_font_dirs() -> dict:
        """List the additional font directories Scribus is configured to scan.

        Reads Scribus's per-user prefs XML (under
        ``%APPDATA%\\Scribus`` on Windows, ``~/.config/scribus`` on Linux,
        ``~/Library/Preferences/Scribus`` on macOS) and returns the paths
        registered under
        ``<context name="Fonts"><table name="ExtraFontDirs">``.

        These take effect on the next Scribus launch — Scribus only scans
        fonts at startup.
        """
        prefs_dir = _scribus_prefs_dir()
        if not prefs_dir:
            return {
                "ok": False,
                "error": "Scribus prefs directory not found. Launch Scribus once so it creates its prefs file.",
                "prefs_dir": None,
                "prefs_xml": None,
                "directories": [],
            }
        prefs_xml = _find_prefs_xml(prefs_dir)
        if not prefs_xml:
            return {
                "ok": False,
                "error": f"No prefs17*.xml file in {prefs_dir}.",
                "prefs_dir": str(prefs_dir),
                "prefs_xml": None,
                "directories": [],
            }
        try:
            tree = ET.parse(str(prefs_xml))
        except ET.ParseError as exc:
            return {
                "ok": False,
                "error": f"could not parse prefs xml: {exc}",
                "prefs_dir": str(prefs_dir),
                "prefs_xml": str(prefs_xml),
                "directories": [],
            }
        table = _font_dirs_table(tree.getroot())
        return {
            "ok": True,
            "error": None,
            "prefs_dir": str(prefs_dir),
            "prefs_xml": str(prefs_xml),
            "directories": _read_extra_font_dirs(table),
        }

    @mcp.tool()
    async def install_custom_font(
        font_path: str,
        target_dir: str = "",
        register_with_scribus: bool = True,
    ) -> dict:
        """Stage a custom font for the next Scribus launch.

        Two-step operation:
          1. Copies the font file (TTF / OTF / TTC / PFA / PFB) into a
             managed directory. Default target is
             ``<runtime_dir>/fonts``, which is owned by scribus-mcp and
             survives across sessions.
          2. If ``register_with_scribus`` is True (default), patches
             Scribus's per-user prefs XML to add the target directory to
             *Additional Font Paths*. A ``.scribus-mcp.bak`` backup is
             written next to the prefs file the first time we touch it,
             so you can roll back if anything looks wrong.

        **Important**: Scribus only scans fonts at startup. The new font
        is invisible to any currently-running Scribus session — the user
        must close and reopen Scribus before it shows up in
        ``list_fonts``.

        Returns the staged font's destination path, the prefs file we
        patched, and a flag indicating whether we needed to add a new
        directory or it was already present.
        """
        src = Path(font_path).expanduser()
        if not src.is_file():
            return {"ok": False, "error": f"font file not found: {src}"}
        if src.suffix.lower() not in _FONT_EXTS:
            return {
                "ok": False,
                "error": f"unsupported font extension {src.suffix!r}; expected one of {sorted(_FONT_EXTS)}",
            }

        # Resolve target directory
        target = Path(target_dir).expanduser() if target_dir else ctx.config.runtime_dir / "fonts"
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"ok": False, "error": f"could not create target dir {target}: {exc}"}

        dest = target / src.name
        try:
            shutil.copy2(str(src), str(dest))
        except OSError as exc:
            return {"ok": False, "error": f"copy failed: {exc}", "target_dir": str(target)}

        result: dict = {
            "ok": True,
            "font": str(dest),
            "target_dir": str(target.resolve()),
            "registered": False,
            "prefs_xml": None,
            "added_directory": False,
            "restart_required": True,
            "note": "Restart Scribus for the new font to appear in list_fonts.",
        }
        if not register_with_scribus:
            return result

        prefs_dir = _scribus_prefs_dir()
        if not prefs_dir:
            result["error"] = (
                "Font copied, but Scribus prefs directory not found — "
                "launch Scribus once first, then call install_custom_font again "
                "(or pass register_with_scribus=false to skip the prefs patch)."
            )
            return result
        prefs_xml = _find_prefs_xml(prefs_dir)
        if not prefs_xml:
            result["error"] = f"Font copied, but no prefs17*.xml in {prefs_dir}."
            return result

        try:
            tree = ET.parse(str(prefs_xml))
        except ET.ParseError as exc:
            result["error"] = f"could not parse prefs xml: {exc}"
            return result

        bak = _backup_path(prefs_xml)
        if not bak.exists():
            try:
                shutil.copy2(str(prefs_xml), str(bak))
            except OSError as exc:
                result["error"] = f"could not write backup: {exc}"
                return result

        table = _font_dirs_table(tree.getroot())
        added = _add_extra_font_dir(table, str(target))
        try:
            tree.write(str(prefs_xml), encoding="UTF-8", xml_declaration=True)
        except OSError as exc:
            result["error"] = f"could not write prefs xml: {exc}"
            return result

        result.update(
            registered=True,
            prefs_xml=str(prefs_xml),
            prefs_backup=str(bak),
            added_directory=added,
        )
        return result

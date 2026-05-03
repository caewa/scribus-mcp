from __future__ import annotations

from importlib import resources
from pathlib import Path

from scribus_mcp.tools._common import ServerCtx


def _load_best_practices() -> str:
    """Return the contents of the BEST_PRACTICES rule sheet.

    Single source of truth: ``doc/BEST_PRACTICES.md`` in the repo. For
    installed wheels we ship the same file as package data at
    ``scribus_mcp/_data/BEST_PRACTICES.md`` (via the ``force-include``
    block in ``pyproject.toml``). Try the package data first, then fall
    back to the dev-tree path for editable installs / source checkouts.
    """
    # 1. Wheel / installed location — read via importlib.resources.
    try:
        pkg_file = resources.files("scribus_mcp").joinpath("_data/BEST_PRACTICES.md")
        if pkg_file.is_file():
            return pkg_file.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    # 2. Dev tree — workflows.py is at src/scribus_mcp/prompts/workflows.py,
    #    so parents[3] is the repo root.
    dev_path = Path(__file__).resolve().parents[3] / "doc" / "BEST_PRACTICES.md"
    try:
        return dev_path.read_text(encoding="utf-8")
    except OSError:
        return (
            "# scribus-mcp — best practices\n\n"
            "BEST_PRACTICES.md not found in this install. See "
            "https://github.com/caewa/scribus-mcp/blob/main/doc/BEST_PRACTICES.md "
            "for the canonical rule sheet."
        )


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.prompt()
    def best_practices() -> str:
        """Rule sheet for driving scribus-mcp.

        Pull this at the start of any session that composes a non-trivial
        Scribus document. Covers: which tool to reach for at each shape,
        coordinate conventions, vertical-flow with PageCursor, accurate
        bboxes, multi-dataset charts, color definitions, markdown
        emphasis, the verify-before-export ritual, and where to find more
        detail (SUPPORT, COOKBOOK).

        Backed by ``doc/BEST_PRACTICES.md`` — single source of truth, so
        the file humans read on GitHub is the same content the LLM
        receives via this prompt.
        """
        return _load_best_practices()

    @mcp.prompt()
    def manual_from_markdown(
        markdown_path: str,
        template_sla: str = "",
        output_pdf: str = "manual.pdf",
    ) -> str:
        """Generate a Scribus manual from a Markdown file using an optional template."""
        return (
            "Generate a printable manual from a Markdown source.\n\n"
            f"Inputs:\n"
            f"- Markdown file: `{markdown_path}`\n"
            f"- Template document: `{template_sla or '(none — create blank A4)'}`\n"
            f"- Output PDF: `{output_pdf}`\n\n"
            "Steps:\n"
            "1. If a template is given, open it; otherwise create a fresh A4 portrait document.\n"
            "2. Read the markdown file's contents.\n"
            "3. Call `import_markdown` with the contents and any paragraph styles the template defines\n"
            "   (use the `scribus://document/info` resource to inspect). For long content, add pages\n"
            "   and link the resulting text frames with `link_text_frames` so text reflows.\n"
            "4. Call `preflight_check` and the `scribus://document/missing-resources` resource. Fix\n"
            "   any missing images or fonts; re-run preflight until clean.\n"
            "5. Call `render_page_to_image` for page 1 and inspect the rendered preview to confirm\n"
            "   the layout looks right. Iterate if needed.\n"
            "6. Call `export_pdf` with the output path.\n"
            "7. Save the .sla alongside the PDF.\n\n"
            "Report the final PDF path and any preflight warnings that remain."
        )

    @mcp.prompt()
    def data_merge_csv(
        template_sla: str,
        csv_path: str,
        output_dir: str = ".",
        placeholder_pattern: str = "%field%",
    ) -> str:
        """Generate one PDF per row of a CSV, substituting placeholders in a template."""
        return (
            f"Generate one PDF per row of `{csv_path}` using `{template_sla}` as the template.\n\n"
            f"For each row:\n"
            f"1. Open the template (`open_document`).\n"
            f"2. For each column, replace `{placeholder_pattern.replace('field', '<column>')}` "
            f"with the row value via `find_and_replace_text` (scope='document').\n"
            "3. Run `preflight_check`; if any text overflow is reported, log it but continue.\n"
            f"4. Export to `{output_dir}/<row-key>.pdf` via `export_pdf`.\n"
            "5. Close the document without saving.\n\n"
            "Report the count of rows processed and any rows that produced preflight errors."
        )

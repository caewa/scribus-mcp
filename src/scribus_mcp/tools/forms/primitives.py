"""All 6 PDF form-field primitives, wrapping createPdfAnnotation.

Scribus encodes the field type as an integer ``which``:
    0 PDFBUTTON       (push button)
    1 PDFRADIOBUTTON  (radio button — group via shared "name" prefix)
    2 PDFTEXTFIELD    (text input)
    3 PDFCHECKBOX
    4 PDFCOMBOBOX     (dropdown)
    5 PDFLISTBOX      (list box)
    6 PDFTEXTANNOTATION (sticky note — see annotations.py)
    7 PDFLINKANNOTATION (link — see annotations.py)
    8 PDF3DANNOTATION   (requires OSG)

Each tool here returns the new annotation's name. Use ``set_js_action`` to
attach JavaScript event handlers, or ``set_form_default_text`` to give text
fields an initial value.
"""

from __future__ import annotations

from scribus_mcp.tools._common import Mode, ServerCtx, get_backend

# Field-type codes per createPdfAnnotation docs
PDF_BUTTON = 0
PDF_RADIO = 1
PDF_TEXTFIELD = 2
PDF_CHECKBOX = 3
PDF_COMBOBOX = 4
PDF_LISTBOX = 5


async def _create_field(
    backend,
    which: int,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    name: str = "",
) -> dict:
    args = (which, x_mm, y_mm, width_mm, height_mm)
    if name:
        result = await backend.call("createPdfAnnotation", *args, name)
    else:
        result = await backend.call("createPdfAnnotation", *args)
    return {"ok": result.ok, "name": result.unwrap_or(), "error": result.error}


def register(mcp, ctx: ServerCtx) -> None:
    @mcp.tool()
    async def create_pdf_text_field(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        default_value: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Single-line text input field. Returns the field's name.

        Optional ``default_value`` is shown when the form is opened.
        """
        backend = await get_backend(ctx, mode)
        r = await _create_field(backend, PDF_TEXTFIELD, x_mm, y_mm, width_mm, height_mm, name)
        if not r.get("ok") or not r.get("name"):
            return r
        if default_value:
            await backend.call("setText", default_value, r["name"])
        return r

    @mcp.tool()
    async def create_pdf_checkbox(
        x_mm: float,
        y_mm: float,
        width_mm: float = 4.0,
        height_mm: float = 4.0,
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Boolean checkbox. Default size 4×4 mm. Returns the field's name."""
        backend = await get_backend(ctx, mode)
        return await _create_field(backend, PDF_CHECKBOX, x_mm, y_mm, width_mm, height_mm, name)

    @mcp.tool()
    async def create_pdf_radio_button(
        x_mm: float,
        y_mm: float,
        width_mm: float = 4.0,
        height_mm: float = 4.0,
        name: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Radio button. Buttons that share the same field NAME prefix in
        Scribus's PDF export form a single mutually-exclusive group. Default
        size 4×4 mm. Returns the field's name.
        """
        backend = await get_backend(ctx, mode)
        return await _create_field(backend, PDF_RADIO, x_mm, y_mm, width_mm, height_mm, name)

    @mcp.tool()
    async def create_pdf_combo_box(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 6.0,
        name: str = "",
        options: list[str] | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """Combo box (dropdown). Options are passed as a list of strings.
        Scribus stores combo-box options inside the .sla; we set them via
        setText with newlines as the canonical encoding the form export
        machinery understands.

        The options apply via a separate ``setText`` call after creation.
        If that call fails, the result still carries ``ok=True`` (the
        field was created) but adds ``options_applied=False`` and
        ``options_error`` so the caller can detect the partial state.
        """
        backend = await get_backend(ctx, mode)
        r = await _create_field(backend, PDF_COMBOBOX, x_mm, y_mm, width_mm, height_mm, name)
        if not r.get("ok") or not r.get("name"):
            return r
        if options:
            opt_res = await backend.call("setText", "\n".join(options), r["name"])
            r["options_applied"] = bool(opt_res.ok)
            if not opt_res.ok:
                r["options_error"] = opt_res.error
        return r

    @mcp.tool()
    async def create_pdf_list_box(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        name: str = "",
        options: list[str] | None = None,
        mode: Mode = "auto",
    ) -> dict:
        """List box (multi-row scrollable list). Same options-as-newlines
        convention as combo box. Returns the field's name. Surfaces
        ``options_applied`` / ``options_error`` if the post-creation
        ``setText`` call fails."""
        backend = await get_backend(ctx, mode)
        r = await _create_field(backend, PDF_LISTBOX, x_mm, y_mm, width_mm, height_mm, name)
        if not r.get("ok") or not r.get("name"):
            return r
        if options:
            opt_res = await backend.call("setText", "\n".join(options), r["name"])
            r["options_applied"] = bool(opt_res.ok)
            if not opt_res.ok:
                r["options_error"] = opt_res.error
        return r

    @mcp.tool()
    async def create_pdf_push_button(
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float = 8.0,
        name: str = "",
        label: str = "",
        action_js: str = "",
        mode: Mode = "auto",
    ) -> dict:
        """Push button. ``label`` becomes the button's caption (set via
        setText). ``action_js`` is optional JavaScript run on Mouse Up
        (event 0) — typical use cases: ``"this.print()"`` for a print
        button, ``"this.resetForm()"`` for reset.

        ``label_applied`` / ``js_applied`` flags surface in the result
        when the post-creation calls fail (with ``label_error`` /
        ``js_error`` for the underlying message).
        """
        backend = await get_backend(ctx, mode)
        r = await _create_field(backend, PDF_BUTTON, x_mm, y_mm, width_mm, height_mm, name)
        if not r.get("ok") or not r.get("name"):
            return r
        if label:
            lbl_res = await backend.call("setText", label, r["name"])
            r["label_applied"] = bool(lbl_res.ok)
            if not lbl_res.ok:
                r["label_error"] = lbl_res.error
        if action_js:
            js_res = await backend.call("setJSActionScript", 0, action_js, r["name"])
            r["js_applied"] = bool(js_res.ok)
            if not js_res.ok:
                r["js_error"] = js_res.error
        return r

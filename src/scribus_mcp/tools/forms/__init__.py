"""PDF form fields, annotations, and JavaScript action handlers.

What's here:
  Form fields  — text input, checkbox, radio, combo box, list box, button.
                 Each wraps Scribus's createPdfAnnotation(which, ...) with a
                 sensible "which" code and field-appropriate defaults.

  Annotations  — link-to-page, link-to-uri, link-to-file, sticky note.
                 These convert an existing text frame into the chosen
                 annotation via Scribus's setLinkAnnotation /
                 setURIAnnotation / setFileAnnotation / setTextAnnotation.

  JS actions   — set / get JavaScript handlers on form fields.
                 Events: mouse up/down/enter/exit, focus in/out, selection
                 change, field format/validate/calculate.
"""

from scribus_mcp.tools.forms import (
    annotations,
    js_action,
    primitives,
)


def register(mcp, ctx) -> None:
    primitives.register(mcp, ctx)
    annotations.register(mcp, ctx)
    js_action.register(mcp, ctx)

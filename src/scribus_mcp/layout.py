"""Page-layout helpers for scripts that drive the MCP.

The MCP server itself doesn't need a vertical-flow tool — when an LLM
drives it, each tool's returned bbox is enough to chain the next call.
But Python scripts that orchestrate many MCP calls (the demo scripts in
``scripts/``, user-side automation, batch generators) end up hand-coding
``y`` values per band, which is bug-prone: a single miscounted band
ripples wrong all the way down the page.

``PageCursor`` centralizes the y-arithmetic so a script declares the
sequence of bands and the helper does the math.

Typical usage::

    from scribus_mcp.layout import PageCursor

    pc = PageCursor(x_mm=12, y_mm=22, width_mm=186, default_gap_mm=4)

    # band() allocates a full-width row, advances cursor by
    # height_mm + default_gap_mm.
    await t("create_text_frame", **pc.band(height_mm=14))

    # split() allocates N side-by-side slots at the same y; cursor
    # advances by height_mm + default_gap_mm.
    left, right = pc.split([90, 90], inner_gap_mm=6, height_mm=45)
    await t("create_bar_chart", **left, ...)

Each slot dict carries both top-left coords (for tools that take
``x_mm`` / ``y_mm`` / ``width_mm`` / ``height_mm``) and center coords
(``center_x`` / ``center_y`` for ``create_pie_chart``,
``create_radar_chart``, ``create_dot_label``, etc.). Splat what you
need.

Pass ``gap_mm=0`` (or any explicit value) on a single ``band`` /
``split`` call to override ``default_gap_mm`` for that band only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# Sentinel meaning "use the cursor's default_gap_mm". Lets band/split
# distinguish "caller passed gap_mm=0 (no gap)" from "caller didn't
# specify (use default)".
_USE_DEFAULT = object()


def _slot(x_mm: float, y_mm: float, width_mm: float, height_mm: float) -> dict:
    """The dict shape that all primitive frame-creating tools accept.

    Includes ``center_x`` / ``center_y`` keys for use with patterns that
    take center coords (pie chart, radar chart, dot label).
    """
    return {
        "x_mm": x_mm,
        "y_mm": y_mm,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "center_x": x_mm + width_mm / 2,
        "center_y": y_mm + height_mm / 2,
    }


@dataclass
class PageCursor:
    """Tracks the running y for a single column on a page.

    ``x_mm`` and ``width_mm`` are the column geometry; ``y_mm`` is the
    cursor's current top (mutates as bands are allocated).
    ``default_gap_mm`` is the vertical gap auto-inserted after every
    band/split call when the caller doesn't pass an explicit ``gap_mm``.
    """

    x_mm: float
    y_mm: float
    width_mm: float
    default_gap_mm: float = 0.0

    def band(self, height_mm: float, gap_mm=_USE_DEFAULT) -> dict:
        """Allocate a full-width band ``height_mm`` tall.

        Returns the slot dict (``x_mm``, ``y_mm``, ``width_mm``,
        ``height_mm``, plus ``center_x`` / ``center_y`` for convenience),
        then advances the cursor by ``height_mm`` plus a gap. The gap is
        ``gap_mm`` if passed; otherwise ``self.default_gap_mm``.
        """
        slot = _slot(self.x_mm, self.y_mm, self.width_mm, height_mm)
        gap = self.default_gap_mm if gap_mm is _USE_DEFAULT else gap_mm
        self.y_mm += height_mm + gap
        return slot

    def gap(self, mm: float) -> None:
        """Advance the cursor without allocating anything."""
        self.y_mm += mm

    def jump_to(self, y_mm: float) -> None:
        """Hard-set the cursor (use when starting a new page)."""
        self.y_mm = y_mm

    def split(
        self,
        widths_mm: Iterable[float],
        inner_gap_mm: float = 0.0,
        height_mm: float | None = None,
        gap_mm=_USE_DEFAULT,
    ) -> list[dict]:
        """Allocate side-by-side slots at the current y.

        ``widths_mm`` is the per-column width list; ``inner_gap_mm`` goes
        between columns. Total must fit within ``self.width_mm`` (raises
        ``ValueError`` otherwise — early failure beats silently drawing
        off the page).

        If ``height_mm`` is given, all slots get that height and the
        cursor advances by ``height_mm`` plus a vertical gap (``gap_mm``
        if passed, else ``self.default_gap_mm``). If ``height_mm`` is
        None, the slots have ``height_mm=0`` and the cursor doesn't
        advance — the caller is expected to fill each column independently
        and call ``jump_to`` when done.
        """
        widths = list(widths_mm)
        gap_total = inner_gap_mm * max(0, len(widths) - 1)
        if sum(widths) + gap_total > self.width_mm + 0.001:
            raise ValueError(
                f"split widths total {sum(widths) + gap_total:.2f} mm exceeds "
                f"column width {self.width_mm:.2f} mm"
            )
        h = height_mm or 0.0
        slots: list[dict] = []
        x = self.x_mm
        for w in widths:
            slots.append(_slot(x, self.y_mm, w, h))
            x += w + inner_gap_mm
        if height_mm is not None:
            extra = self.default_gap_mm if gap_mm is _USE_DEFAULT else gap_mm
            self.y_mm += height_mm + extra
        return slots

    @property
    def y(self) -> float:
        """Read-only alias for ``y_mm`` — handy in expressions."""
        return self.y_mm


__all__ = ["PageCursor"]

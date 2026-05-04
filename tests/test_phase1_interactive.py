"""Phase 1 — interactive backend integration tests.

These tests require a *running* Scribus + bridge. They are skipped by
default. To run them:

  1. Install matching PyQt6 (Windows: scripts/install-pyqt-windows.ps1).
  2. Launch Scribus with the bridge:
     - Linux:   scribus --console -py "$(scribus-mcp --print-bridge-path)"
     - Windows: & "C:\\Program Files\\Scribus 1.7.3\\scribus.exe" --console -py
                "C:\\Users\\<you>\\scribus-mcp\\src\\scribus_mcp\\bridge\\scribus_mcp_bridge.spy"
  3. Dismiss the welcome dialog.
  4. Run: SCRIBUS_MCP_LIVE=1 pytest tests/test_phase1_interactive.py -v

The tests use the live MCP server's call_tool path so they exercise the
same code Claude would.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from scribus_mcp.testing import unwrap as _unwrap

LIVE = os.environ.get("SCRIBUS_MCP_LIVE") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="Live Scribus + bridge not available (set SCRIBUS_MCP_LIVE=1 to enable)",
)


@pytest.fixture(scope="module")
def mcp():
    from scribus_mcp.server import build_server

    return build_server()


@pytest.fixture(scope="module")
def call(mcp):
    async def _call(tool_name: str, **kwargs):
        return _unwrap(await mcp.call_tool(tool_name, kwargs))

    return _call


@pytest.fixture(scope="module")
def bridge_alive():
    """Confirm the interactive bridge is reachable. Skips the module if not."""
    from scribus_mcp.backends import InteractiveBackend
    from scribus_mcp.config import Config

    backend = InteractiveBackend(Config.from_env())
    if not asyncio.run(backend.is_available()):
        pytest.skip("Bridge not reachable (no discovery file or port not listening)")
    return backend


# ----- Section 1.A — bridge bring-up ---------------------------------------


def test_1A6_ping(bridge_alive):
    r = asyncio.run(bridge_alive._send({"kind": "ping"}))
    assert r.ok and r.value == "pong"


# ----- Section 1.C — document lifecycle -----------------------------------


def test_1C1_create_document(call):
    r = asyncio.run(call("create_document", mode="interactive"))
    assert r.get("ok") is True


def test_1C2_get_document_info(call):
    r = asyncio.run(call("get_document_info", mode="interactive"))
    assert r.get("ok") is True
    info = r["value"]
    assert info["has_doc"] is True
    assert info["page_count"] >= 1


def test_1C3_set_document_metadata(call):
    r = asyncio.run(
        call("set_document_metadata", title="T", author="A", description="D", mode="interactive")
    )
    assert r.get("ok") is True


def test_1C4_save_document_as(call, tmp_path):
    sla = tmp_path / "out.sla"
    r = asyncio.run(call("save_document_as", path=str(sla), mode="interactive"))
    assert r.get("ok") is True
    assert sla.exists()


# ----- Section 1.D — pages -------------------------------------------------


def test_1D1_add_page(call):
    r = asyncio.run(call("add_page", mode="interactive"))
    assert r.get("ok") is True


def test_1D2_page_count(call):
    r = asyncio.run(call("get_page_count", mode="interactive"))
    assert isinstance(r.get("value"), int) and r["value"] >= 1


# ----- Section 1.E — frames ------------------------------------------------


def test_1E1_create_text_frame(call):
    r = asyncio.run(
        call("create_text_frame", x_mm=10, y_mm=10, width_mm=100, height_mm=40, mode="interactive")
    )
    assert r.get("name")


def test_1E2_create_image_frame(call):
    r = asyncio.run(
        call("create_image_frame", x_mm=10, y_mm=60, width_mm=80, height_mm=50, mode="interactive")
    )
    assert r.get("name")


def test_1E7_list_page_objects(call):
    r = asyncio.run(call("list_page_objects", mode="interactive"))
    assert isinstance(r.get("items"), list) and len(r["items"]) >= 2


# ----- Section 1.F — text content & flow ----------------------------------


@pytest.fixture(scope="module")
def text_frame(call):
    r = asyncio.run(
        call("create_text_frame", x_mm=20, y_mm=120, width_mm=120, height_mm=40, mode="interactive")
    )
    name = r["name"]
    asyncio.run(call("set_text", name=name, text="round-trip", mode="interactive"))
    return name


def test_1F1_set_text(text_frame, call):
    r = asyncio.run(call("set_text", name=text_frame, text="Hello", mode="interactive"))
    assert r.get("ok") is True


def test_1F2_get_text_round_trip(text_frame, call):
    asyncio.run(call("set_text", name=text_frame, text="payload-XYZ", mode="interactive"))
    r = asyncio.run(call("get_text", name=text_frame, mode="interactive"))
    assert r.get("text") == "payload-XYZ"


def test_1F4_not_overflowing(text_frame, call):
    asyncio.run(call("set_text", name=text_frame, text="short", mode="interactive"))
    r = asyncio.run(call("is_text_overflowing", name=text_frame, mode="interactive"))
    assert r.get("overflowing") is False


def test_1F5_overflow_detected(text_frame, call):
    asyncio.run(call("set_text", name=text_frame, text="Lorem ipsum " * 200, mode="interactive"))
    r = asyncio.run(call("is_text_overflowing", name=text_frame, mode="interactive"))
    assert r.get("overflowing") is True


# ----- Section 1.G — text formatting ---------------------------------------


def test_1G3_set_font_size(text_frame, call):
    r = asyncio.run(call("set_font_size", name=text_frame, size_pt=18, mode="interactive"))
    assert r.get("ok") is True


def test_1G6_set_text_alignment(text_frame, call):
    r = asyncio.run(
        call("set_text_alignment", name=text_frame, alignment="center", mode="interactive")
    )
    assert r.get("ok") is True


# ----- Section 1.H — styles ------------------------------------------------


def test_1H1_list_paragraph_styles(call):
    r = asyncio.run(call("list_paragraph_styles", mode="interactive"))
    assert isinstance(r.get("styles"), list) and len(r["styles"]) >= 1


def test_1H1b_list_character_styles(call):
    r = asyncio.run(call("list_character_styles", mode="interactive"))
    assert isinstance(r.get("styles"), list)


# ----- Section 1.I — colors ------------------------------------------------


def test_1I1_list_colors(call):
    r = asyncio.run(call("list_colors", mode="interactive"))
    colors = r.get("colors") or []
    assert "Black" in colors and len(colors) >= 5


def test_1I2_define_color_cmyk(call):
    r = asyncio.run(
        call(
            "define_color_cmyk",
            name="Brand",
            cyan=80,
            magenta=0,
            yellow=20,
            key=0,
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1I3_define_color_rgb(call):
    r = asyncio.run(
        call("define_color_rgb", name="Accent", red=200, green=80, blue=80, mode="interactive")
    )
    assert r.get("ok") is True


# ----- Section 1.K — layers ------------------------------------------------


def test_1K1_list_layers(call):
    r = asyncio.run(call("list_layers", mode="interactive"))
    assert isinstance(r.get("layers"), list) and len(r["layers"]) >= 1


def test_1K2_create_layer(call):
    r = asyncio.run(call("create_layer", name="MCP-test-layer", mode="interactive"))
    assert r.get("ok") is True


def test_1K3_set_active_layer(call):
    r = asyncio.run(call("set_active_layer", name="MCP-test-layer", mode="interactive"))
    assert r.get("ok") is True


# ----- Section 1.L — search ------------------------------------------------


def test_1L1_find_and_replace_document(text_frame, call):
    asyncio.run(call("set_text", name=text_frame, text="replace foo with bar", mode="interactive"))
    r = asyncio.run(
        call(
            "find_and_replace_text",
            target="foo",
            replacement="BAR",
            scope="document",
            mode="interactive",
        )
    )
    assert r.get("replacements") >= 1


def test_1L4_find_objects_by_type(call):
    r = asyncio.run(call("find_objects", object_type="text", mode="interactive"))
    assert isinstance(r.get("objects"), list)


# ----- Section 1.M — export ------------------------------------------------


def test_1M1_export_pdf(call, tmp_path):
    pdf = tmp_path / "out.pdf"
    r = asyncio.run(call("export_pdf", path=str(pdf), mode="interactive"))
    assert r.get("ok") is True
    assert pdf.exists() and pdf.stat().st_size > 1000


def test_1M5_render_page_to_image(mcp):
    """Returns inline image content (base64 PNG) and a description text."""
    out = asyncio.run(
        mcp.call_tool("render_page_to_image", {"page_number": 1, "dpi": 96, "mode": "interactive"})
    )
    # FastMCP returns (content_list, structured) tuple here
    content_list = out[0] if isinstance(out, tuple) else out
    assert isinstance(content_list, list) and len(content_list) >= 1
    types = [getattr(c, "type", None) for c in content_list]
    assert "image" in types, f"expected an ImageContent in result, got types={types}"
    img = next(c for c in content_list if getattr(c, "type", None) == "image")
    assert getattr(img, "mimeType", None) == "image/png"
    assert len(getattr(img, "data", "") or "") > 100, (
        "image data should be non-trivially long base64"
    )


def test_1M7_preflight_check(call):
    r = asyncio.run(call("preflight_check", mode="interactive"))
    assert r.get("ok") is True
    report = r.get("report") or {}
    assert "issues" in report


# ----- Section 1.S — shapes (NEW) -----------------------------------------


def test_1S1_create_rectangle(call):
    r = asyncio.run(
        call("create_rectangle", x_mm=10, y_mm=200, width_mm=50, height_mm=20, mode="interactive")
    )
    assert r.get("name")


def test_1S2_create_ellipse(call):
    r = asyncio.run(
        call("create_ellipse", x_mm=70, y_mm=200, width_mm=40, height_mm=20, mode="interactive")
    )
    assert r.get("name")


def test_1S3_create_line(call):
    r = asyncio.run(
        call("create_line", x1_mm=10, y1_mm=230, x2_mm=110, y2_mm=230, mode="interactive")
    )
    assert r.get("name")


def test_1S4_create_polygon(call):
    r = asyncio.run(
        call("create_polygon", points_mm=[120, 200, 150, 200, 135, 230], mode="interactive")
    )
    assert r.get("name")


def test_1S5_create_polyline(call):
    r = asyncio.run(
        call(
            "create_polyline",
            points_mm=[160, 200, 175, 215, 190, 200, 200, 230],
            mode="interactive",
        )
    )
    assert r.get("name")


def test_1S6_polygon_validation_too_few_points(call):
    r = asyncio.run(call("create_polygon", points_mm=[1, 2, 3, 4], mode="interactive"))
    assert r.get("ok") is False
    assert "at least" in r.get("error", "")


# ----- Section 1.T — styling (NEW) ----------------------------------------


@pytest.fixture(scope="module")
def styling_target(call):
    """A rectangle dedicated to styling round-trip tests."""
    r = asyncio.run(
        call("create_rectangle", x_mm=10, y_mm=255, width_mm=50, height_mm=15, mode="interactive")
    )
    return r["name"]


def test_1T1_set_fill_color(styling_target, call):
    r = asyncio.run(call("set_fill_color", name=styling_target, color="Black", mode="interactive"))
    assert r.get("ok") is True


def test_1T2_get_fill_color_round_trip(styling_target, call):
    asyncio.run(call("set_fill_color", name=styling_target, color="Black", mode="interactive"))
    r = asyncio.run(call("get_fill_color", name=styling_target, mode="interactive"))
    assert r.get("color") == "Black"


def test_1T3_set_line_color(styling_target, call):
    r = asyncio.run(call("set_line_color", name=styling_target, color="None", mode="interactive"))
    assert r.get("ok") is True


def test_1T4_set_line_width(styling_target, call):
    r = asyncio.run(call("set_line_width", name=styling_target, width_pt=1.5, mode="interactive"))
    assert r.get("ok") is True


def test_1T5_set_line_style_dashed(styling_target, call):
    r = asyncio.run(call("set_line_style", name=styling_target, style="dash", mode="interactive"))
    assert r.get("ok") is True


def test_1T6_set_corner_radius(styling_target, call):
    r = asyncio.run(call("set_corner_radius", name=styling_target, radius_pt=4, mode="interactive"))
    assert r.get("ok") is True


def test_1T7_set_fill_transparency(styling_target, call):
    r = asyncio.run(
        call("set_fill_transparency", name=styling_target, opacity=0.5, mode="interactive")
    )
    assert r.get("ok") is True


def test_1T8_set_fill_transparency_validation(styling_target, call):
    r = asyncio.run(
        call("set_fill_transparency", name=styling_target, opacity=2.0, mode="interactive")
    )
    assert r.get("ok") is False


def test_1T9_set_line_style_validation(styling_target, call):
    r = asyncio.run(call("set_line_style", name=styling_target, style="bogus", mode="interactive"))
    assert r.get("ok") is False


def test_1T10_apply_gradient_horizontal(styling_target, call):
    r = asyncio.run(
        call(
            "apply_gradient",
            name=styling_target,
            type="horizontal",
            color1="Black",
            color2="White",
            shade1=100,
            shade2=80,
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1T11_apply_gradient_radial(styling_target, call):
    r = asyncio.run(
        call(
            "apply_gradient",
            name=styling_target,
            type="radial",
            color1="Black",
            color2="White",
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1T12_apply_gradient_validation(styling_target, call):
    r = asyncio.run(call("apply_gradient", name=styling_target, type="bogus", mode="interactive"))
    assert r.get("ok") is False
    assert "type must be one of" in r.get("error", "")


def test_1T13_clear_gradient(styling_target, call):
    r = asyncio.run(call("clear_gradient", name=styling_target, mode="interactive"))
    assert r.get("ok") is True


# ----- Section 1.U — high-level patterns ----------------------------------


def test_1U1_create_radar_chart(call):
    """Drop a 5-axis competency radar onto the page."""
    r = asyncio.run(
        call(
            "create_radar_chart",
            axes=["Python", "Scribus", "PDF", "Linux", "MCP"],
            values=[0.9, 0.6, 0.7, 0.85, 0.95],
            center_x_mm=150,
            center_y_mm=160,
            radius_mm=30,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("data_polygon")
    assert len(r.get("rings") or []) == 4
    assert len(r.get("axes") or []) == 5
    assert len(r.get("labels") or []) == 5


def test_1U2_radar_chart_validation_mismatched_lengths(call):
    r = asyncio.run(
        call(
            "create_radar_chart",
            axes=["A", "B", "C"],
            values=[0.5, 0.7],
            center_x_mm=100,
            center_y_mm=100,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "same length" in r.get("error", "")


def test_1U3_radar_chart_too_few_axes(call):
    r = asyncio.run(
        call(
            "create_radar_chart",
            axes=["A", "B"],
            values=[0.5, 0.7],
            center_x_mm=100,
            center_y_mm=100,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "at least 3" in r.get("error", "")


def test_1U3b_create_radar_chart_multi_dataset(call):
    """Two-dataset overlay (Plan vs Actual) + legend below."""
    r = asyncio.run(
        call(
            "create_radar_chart",
            axes=["Coverage", "Speed", "Reliability", "DX", "Docs"],
            datasets=[
                {
                    "label": "Plan",
                    "values": [0.8, 0.7, 0.9, 0.6, 0.5],
                    "fill_color": "Black",
                    "fill_shade": 25,
                    "line_color": "Black",
                    "fill_alpha": 0.5,
                },
                {
                    "label": "Actual",
                    "values": [0.95, 0.85, 0.9, 0.8, 0.7],
                    "fill_color": "Black",
                    "fill_shade": 60,
                    "line_color": "Black",
                    "fill_alpha": 0.5,
                },
            ],
            center_x_mm=100,
            center_y_mm=200,
            radius_mm=24,
            mode="interactive",
        )
    )
    assert r.get("ok") is True, r.get("error")
    assert r.get("n_datasets") == 2
    assert len(r.get("data_polygons") or []) == 2
    # Single-dataset back-compat key should be None for multi.
    assert r.get("data_polygon") is None
    # Legend: 2 datasets × (swatch + label) = 4 objects.
    assert len(r.get("legend") or []) == 4


def test_1U3c_radar_chart_dataset_length_mismatch(call):
    r = asyncio.run(
        call(
            "create_radar_chart",
            axes=["A", "B", "C", "D"],
            datasets=[{"label": "x", "values": [0.5, 0.7], "fill_color": "Black"}],
            center_x_mm=100,
            center_y_mm=100,
            radius_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "length 4" in (r.get("error") or "")


def test_1U3d_radar_chart_values_and_datasets_both(call):
    r = asyncio.run(
        call(
            "create_radar_chart",
            axes=["A", "B", "C"],
            values=[0.5, 0.6, 0.7],
            datasets=[{"label": "x", "values": [0.1, 0.2, 0.3], "fill_color": "Black"}],
            center_x_mm=100,
            center_y_mm=100,
            radius_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "either values OR datasets" in (r.get("error") or "")


def test_1U4_create_bar_chart(call):
    r = asyncio.run(
        call(
            "create_bar_chart",
            labels=["Q1", "Q2", "Q3", "Q4"],
            values=[12, 18, 9, 25],
            x_mm=20,
            y_mm=20,
            width_mm=80,
            height_mm=40,
            show_values=True,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert len(r.get("bars") or []) == 4
    assert len(r.get("labels") or []) == 4
    assert len(r.get("value_labels") or []) == 4


def test_1U5_bar_chart_validation(call):
    r = asyncio.run(
        call(
            "create_bar_chart",
            labels=["A", "B", "C"],
            values=[1, 2],
            x_mm=10,
            y_mm=10,
            width_mm=20,
            height_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1U4b_create_bar_chart_multi_dataset(call):
    """Grouped bar chart: 4 categories × 3 datasets + legend strip below."""
    r = asyncio.run(
        call(
            "create_bar_chart",
            labels=["Q1", "Q2", "Q3", "Q4"],
            datasets=[
                {
                    "label": "2024",
                    "values": [10, 12, 8, 14],
                    "fill_color": "Black",
                    "fill_shade": 60,
                },
                {
                    "label": "2025",
                    "values": [12, 18, 9, 17],
                    "fill_color": "Black",
                    "fill_shade": 80,
                },
                {
                    "label": "2026",
                    "values": [15, 22, 14, 25],
                    "fill_color": "Black",
                    "fill_shade": 100,
                },
            ],
            x_mm=20,
            y_mm=70,
            width_mm=120,
            height_mm=50,
            mode="interactive",
        )
    )
    assert r.get("ok") is True, r.get("error")
    # 4 categories × 3 datasets = 12 bars
    assert len(r.get("bars") or []) == 12
    # 4 category labels under the bars
    assert len(r.get("labels") or []) == 4
    # 3 datasets × (swatch + label) = 6 legend objects
    assert len(r.get("legend") or []) == 6
    assert r.get("n_datasets") == 3


def test_1U4c_create_bar_chart_dataset_length_mismatch(call):
    r = asyncio.run(
        call(
            "create_bar_chart",
            labels=["A", "B", "C"],
            datasets=[{"label": "x", "values": [1, 2], "fill_color": "Black"}],
            x_mm=10,
            y_mm=10,
            width_mm=20,
            height_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "length 3" in (r.get("error") or "")


def test_1U4d_bar_chart_values_and_datasets_both(call):
    r = asyncio.run(
        call(
            "create_bar_chart",
            labels=["A", "B"],
            values=[1, 2],
            datasets=[{"label": "x", "values": [3, 4], "fill_color": "Black"}],
            x_mm=10,
            y_mm=10,
            width_mm=20,
            height_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "either values OR datasets" in (r.get("error") or "")


def test_1U6_create_pie_chart(call):
    r = asyncio.run(
        call(
            "create_pie_chart",
            labels=["A", "B", "C", "D"],
            values=[40, 30, 20, 10],
            center_x_mm=50,
            center_y_mm=80,
            radius_mm=20,
            show_legend=True,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert len(r.get("slices") or []) == 4


def test_1U7_pie_chart_zero_total(call):
    r = asyncio.run(
        call(
            "create_pie_chart",
            labels=["A", "B"],
            values=[0, 0],
            center_x_mm=50,
            center_y_mm=80,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1U8_create_timeline(call):
    items = [
        {"position": 0.0, "label": "Kickoff", "date": "2026-01"},
        {"position": 0.33, "label": "Alpha", "date": "2026-03"},
        {"position": 0.66, "label": "Beta", "date": "2026-06"},
        {"position": 1.0, "label": "Launch", "date": "2026-09"},
    ]
    r = asyncio.run(
        call(
            "create_timeline", items=items, x_mm=20, axis_y_mm=120, width_mm=160, mode="interactive"
        )
    )
    assert r.get("ok") is True
    assert r.get("axis")
    assert len(r.get("markers") or []) == 4
    assert len(r.get("dates") or []) == 4
    # connectors are on by default
    assert len(r.get("connectors") or []) == 4
    # bbox now reflects the full label-above + axis + date-below footprint
    bbox = r.get("bbox") or {}
    assert bbox.get("y_mm") is not None and bbox.get("height_mm")


def test_1U8b_create_timeline_top_y_mm(call):
    """top_y_mm is the friendlier slot-aligned variant."""
    items = [{"position": 0.0, "label": "Start"}, {"position": 1.0, "label": "End"}]
    r = asyncio.run(
        call(
            "create_timeline", items=items, x_mm=20, top_y_mm=140, width_mm=120, mode="interactive"
        )
    )
    assert r.get("ok") is True
    bbox = r.get("bbox") or {}
    # bbox top should be == top_y_mm (the slot top we passed in)
    assert abs((bbox.get("y_mm") or 0) - 140) < 0.5


def test_1U9_timeline_missing_keys(call):
    r = asyncio.run(
        call(
            "create_timeline",
            items=[{"label": "no position"}],
            x_mm=10,
            axis_y_mm=10,
            width_mm=50,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1U9b_timeline_requires_one_y_param(call):
    items = [{"position": 0.0, "label": "x"}]
    r = asyncio.run(call("create_timeline", items=items, x_mm=10, width_mm=50, mode="interactive"))
    assert r.get("ok") is False
    assert "top_y_mm or axis_y_mm" in (r.get("error") or "")


def test_1U9c_timeline_rejects_both_y_params(call):
    items = [{"position": 0.0, "label": "x"}]
    r = asyncio.run(
        call(
            "create_timeline",
            items=items,
            x_mm=10,
            width_mm=50,
            top_y_mm=20,
            axis_y_mm=30,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "only one of" in (r.get("error") or "")


def test_1U10_create_callout_box(call):
    r = asyncio.run(
        call(
            "create_callout_box",
            title="Note",
            body="This is a callout body. Lorem ipsum dolor sit amet.",
            x_mm=20,
            y_mm=200,
            width_mm=80,
            height_mm=30,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("background") and r.get("title") and r.get("body")


def test_1U11_create_kpi_tile(call):
    r = asyncio.run(
        call(
            "create_kpi_tile",
            value="42.7%",
            label="conversion rate",
            x_mm=110,
            y_mm=200,
            width_mm=50,
            height_mm=30,
            delta="+3.2pp vs last month",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("value") and r.get("label") and r.get("delta")


def test_1U12_create_comparison_table(call):
    r = asyncio.run(
        call(
            "create_comparison_table",
            headers=["Tier", "Price", "Seats", "Support"],
            rows=[
                ["Starter", "$12", "1", "Email"],
                ["Pro", "$48", "5", "Chat"],
                ["Enterprise", "Contact", "Unlimited", "Phone"],
            ],
            x_mm=20,
            y_mm=240,
            width_mm=170,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("rows_drawn") == 3
    assert len(r.get("headers") or []) == 4


def test_1U13_comparison_table_row_width_mismatch(call):
    r = asyncio.run(
        call(
            "create_comparison_table",
            headers=["A", "B"],
            rows=[["x", "y", "z"]],
            x_mm=20,
            y_mm=270,
            width_mm=50,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "expected" in r.get("error", "")


def test_1U14_create_qr_code_block(call):
    """Best-effort: requires Ghostscript on the system. Skip if missing."""
    r = asyncio.run(
        call(
            "create_qr_code_block",
            data="https://muxen.fr",
            x_mm=160,
            y_mm=80,
            size_mm=20,
            caption="muxen.fr",
            mode="interactive",
        )
    )
    if not r.get("ok"):
        # Skip on:
        #   - Scribus < 1.7 (``required_version`` set by the version gate)
        #   - Ghostscript not installed (Scribus reports it via createBarcode)
        if r.get("required_version"):
            pytest.skip(
                f"Barcode requires Scribus {r.get('required_version')}+; "
                f"this Scribus reports {r.get('actual_version')}"
            )
        err = (r.get("error") or "").lower()
        if "ghostscript" in err or "gs " in err or "createbarcode" in err:
            pytest.skip(f"Barcode unavailable (likely no Ghostscript): {r.get('error')}")
    assert r.get("ok") is True
    assert r.get("barcode")


def test_1U15_create_dot_label(call):
    r = asyncio.run(
        call(
            "create_dot_label",
            text="!",
            center_x_mm=170,
            center_y_mm=210,
            diameter_mm=10,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("circle") and r.get("text")


def test_1U16_create_numbered_badge(call):
    r = asyncio.run(
        call(
            "create_numbered_badge",
            number=7,
            center_x_mm=185,
            center_y_mm=210,
            diameter_mm=10,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("circle") and r.get("text")
    assert r.get("number") == 7


# ----- Section 1.V — layouts (Tier 1) ---------------------------------------


def test_1V1_create_two_column_text(call):
    r = asyncio.run(
        call(
            "create_two_column_text",
            text_left="Lorem ipsum dolor sit amet.",
            text_right="Consectetur adipiscing elit.",
            x_mm=20,
            y_mm=60,
            width_mm=170,
            height_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("left") and r.get("right")
    assert r.get("column_width_mm") > 0


def test_1V2_two_column_validation(call):
    r = asyncio.run(
        call(
            "create_two_column_text",
            text_left="x",
            text_right="y",
            x_mm=10,
            y_mm=10,
            width_mm=5,
            height_mm=10,
            gap_mm=10,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V3_create_text_with_image(call):
    r = asyncio.run(
        call(
            "create_text_with_image",
            text="Caption text alongside the image frame.",
            x_mm=20,
            y_mm=85,
            width_mm=170,
            height_mm=30,
            image_side="left",
            image_ratio=0.35,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("image") and r.get("text")
    assert r.get("image_width_mm") > 0
    assert r.get("text_width_mm") > 0


def test_1V4_text_with_image_validation(call):
    r = asyncio.run(
        call(
            "create_text_with_image",
            text="x",
            x_mm=10,
            y_mm=10,
            width_mm=50,
            height_mm=20,
            image_side="middle",
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V5_create_section_header(call):
    r = asyncio.run(
        call(
            "create_section_header",
            title="Architecture",
            eyebrow="Section 2",
            x_mm=20,
            y_mm=120,
            width_mm=170,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("title")
    assert r.get("eyebrow")
    assert r.get("rule")
    assert r.get("bottom_y_mm") > 120


def test_1V6_section_header_no_eyebrow_no_rule(call):
    r = asyncio.run(
        call(
            "create_section_header",
            title="Plain title",
            x_mm=20,
            y_mm=140,
            width_mm=170,
            with_rule=False,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("title")
    assert r.get("eyebrow") is None
    assert r.get("rule") is None


def test_1V7_create_hero_band(call):
    r = asyncio.run(
        call(
            "create_hero_band",
            title="Drive Scribus from Claude",
            subtitle="A Model Context Protocol server",
            eyebrow="scribus-mcp",
            right_text="v1.0.0",
            x_mm=0,
            y_mm=0,
            width_mm=210,
            height_mm=30,
            fill_color="Black",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("band")
    assert r.get("title")
    assert r.get("subtitle")
    assert r.get("eyebrow")
    assert r.get("right_text")


def test_1V8_create_numbered_steps(call):
    r = asyncio.run(
        call(
            "create_numbered_steps",
            items=[
                {"title": "Install", "body": "pip install -e ."},
                {"title": "Configure", "body": "Add to MCP config"},
                {"title": "Use", "body": "Tell Claude to make a doc"},
            ],
            x_mm=20,
            y_mm=170,
            width_mm=170,
            item_height_mm=22,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("count") == 3
    steps = r.get("steps") or []
    assert len(steps) == 3
    for s in steps:
        assert s.get("circle") and s.get("container")


def test_1V9_numbered_steps_validation(call):
    r = asyncio.run(
        call(
            "create_numbered_steps",
            items=[{"title": "missing body"}],
            x_mm=20,
            y_mm=170,
            width_mm=170,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "body" in r.get("error", "")


def test_1V10_create_image_caption(call):
    r = asyncio.run(
        call(
            "create_image_caption",
            x_mm=20,
            y_mm=210,
            width_mm=80,
            height_mm=40,
            caption="An empty image frame, captioned",
            figure_number=1,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("image") and r.get("caption")
    assert r.get("figure_number") == 1


def test_1V11_image_caption_validation(call):
    r = asyncio.run(
        call(
            "create_image_caption",
            x_mm=20,
            y_mm=210,
            width_mm=80,
            height_mm=10,
            caption_height_mm=12,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V12_create_table_of_contents(call):
    r = asyncio.run(
        call(
            "create_table_of_contents",
            entries=[
                {"title": "Introduction", "page": 1, "level": 0},
                {"title": "Architecture", "page": 4, "level": 0},
                {"title": "Backends", "page": 5, "level": 1},
                {"title": "Tools", "page": 8, "level": 0},
            ],
            x_mm=20,
            y_mm=240,
            width_mm=170,
            title="Contents",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("title")
    assert len(r.get("entries") or []) == 4


def test_1V13_toc_validation(call):
    r = asyncio.run(
        call(
            "create_table_of_contents",
            entries=[],
            x_mm=20,
            y_mm=240,
            width_mm=170,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V14_create_sidebar_layout_left(call):
    r = asyncio.run(
        call(
            "create_sidebar_layout",
            x_mm=20,
            y_mm=10,
            width_mm=170,
            height_mm=40,
            sidebar_side="left",
            sidebar_width_mm=40,
            sidebar_text="Note",
            main_text="Body",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("sidebar_bg") and r.get("sidebar_text") and r.get("main_text")


def test_1V15_create_sidebar_layout_right(call):
    r = asyncio.run(
        call(
            "create_sidebar_layout",
            x_mm=20,
            y_mm=10,
            width_mm=170,
            height_mm=40,
            sidebar_side="right",
            sidebar_width_mm=40,
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1V16_sidebar_validation(call):
    r = asyncio.run(
        call(
            "create_sidebar_layout",
            x_mm=20,
            y_mm=10,
            width_mm=50,
            height_mm=40,
            sidebar_width_mm=60,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V17_create_kpi_row(call):
    r = asyncio.run(
        call(
            "create_kpi_row",
            items=[
                {"value": "12", "label": "uno", "delta": "a"},
                {"value": "34", "label": "dos", "delta": "b"},
                {"value": "56", "label": "tres", "delta": "c"},
                {"value": "78", "label": "cuatro", "delta": "d"},
            ],
            x_mm=20,
            y_mm=60,
            width_mm=170,
            height_mm=30,
            gap_mm=3,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("count") == 4
    assert r.get("tile_width_mm") > 0
    # Auto-computed width should fit: 4 tiles + 3 gaps in 170mm
    expected_w = (170 - 3 * 3) / 4
    assert abs(r["tile_width_mm"] - expected_w) < 0.01


def test_1V18_kpi_row_overflow_validation(call):
    r = asyncio.run(
        call(
            "create_kpi_row",
            items=[{"value": "1", "label": "a"}, {"value": "2", "label": "b"}],
            x_mm=10,
            y_mm=10,
            width_mm=4,
            height_mm=20,
            gap_mm=10,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V19_kpi_row_missing_keys(call):
    r = asyncio.run(
        call(
            "create_kpi_row",
            items=[{"label": "missing value"}],
            x_mm=10,
            y_mm=10,
            width_mm=50,
            height_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V20_create_equal_columns(call):
    r = asyncio.run(
        call(
            "create_equal_columns",
            x_mm=10,
            y_mm=80,
            width_mm=170,
            height_mm=20,
            columns=5,
            gap_mm=4,
            frame_type="text",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    frames = r.get("frames") or []
    assert len(frames) == 5
    expected_w = (170 - 4 * 4) / 5
    assert abs(r["column_width_mm"] - expected_w) < 0.01
    # Check all frames are sequentially placed
    xs = [f["x_mm"] for f in frames]
    assert xs == sorted(xs)


def test_1V21_equal_columns_rectangle_type(call):
    r = asyncio.run(
        call(
            "create_equal_columns",
            x_mm=10,
            y_mm=110,
            width_mm=170,
            height_mm=15,
            columns=3,
            gap_mm=2,
            frame_type="rectangle",
            fill_color="Black",
            fill_shade=10,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert len(r["frames"]) == 3


def test_1V22_equal_columns_validation(call):
    # Invalid frame_type
    r = asyncio.run(
        call(
            "create_equal_columns",
            x_mm=10,
            y_mm=10,
            width_mm=100,
            height_mm=20,
            columns=2,
            gap_mm=2,
            frame_type="bogus",
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V23_create_card_grid(call):
    items = [
        {"title": "Alpha", "body": "first card body"},
        {"title": "Beta", "body": "second card body", "eyebrow": "tagline"},
        {"title": "Gamma", "body": "third", "accent_side": "top"},
        {"title": "Delta", "body": "fourth", "accent_color": "Black"},
    ]
    r = asyncio.run(
        call(
            "create_card_grid",
            items=items,
            x_mm=20,
            y_mm=130,
            width_mm=170,
            height_mm=70,
            columns=2,
            column_gap_mm=4,
            row_gap_mm=4,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("rows") == 2
    assert r.get("columns") == 2
    assert r.get("count") == 4
    assert len(r.get("cards") or []) == 4
    for c in r["cards"]:
        assert c.get("background")
        assert c.get("title")
        assert c.get("body")


def test_1V24_card_grid_three_columns(call):
    """Uneven count: 5 items in 3 columns → 2 rows (last row partial)."""
    items = [{"title": f"T{i}", "body": f"body {i}"} for i in range(5)]
    r = asyncio.run(
        call(
            "create_card_grid",
            items=items,
            x_mm=20,
            y_mm=210,
            width_mm=170,
            height_mm=50,
            columns=3,
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("rows") == 2  # ceil(5/3)
    assert r.get("count") == 5


def test_1V25_card_grid_validation_missing_keys(call):
    r = asyncio.run(
        call(
            "create_card_grid",
            items=[{"title": "missing body"}],
            x_mm=20,
            y_mm=10,
            width_mm=100,
            height_mm=40,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V26_card_grid_validation_bad_accent_side(call):
    r = asyncio.run(
        call(
            "create_card_grid",
            items=[{"title": "x", "body": "y"}],
            x_mm=20,
            y_mm=10,
            width_mm=100,
            height_mm=40,
            accent_side="diagonal",
            mode="interactive",
        )
    )
    assert r.get("ok") is False


def test_1V27_card_grid_overflow_validation(call):
    """Too many gaps for the available width."""
    r = asyncio.run(
        call(
            "create_card_grid",
            items=[{"title": "x", "body": "y"} for _ in range(4)],
            x_mm=10,
            y_mm=10,
            width_mm=10,
            height_mm=40,
            columns=4,
            column_gap_mm=10,
            mode="interactive",
        )
    )
    assert r.get("ok") is False


# ----- Section 1.W — PDF forms ---------------------------------------------


def test_1W1_create_pdf_text_field(call):
    r = asyncio.run(
        call(
            "create_pdf_text_field",
            x_mm=20,
            y_mm=20,
            width_mm=60,
            height_mm=8,
            default_value="hello",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("name")


def test_1W2_create_pdf_checkbox(call):
    r = asyncio.run(call("create_pdf_checkbox", x_mm=20, y_mm=35, mode="interactive"))
    assert r.get("ok") is True
    assert r.get("name")


def test_1W3_create_pdf_radio_button(call):
    r = asyncio.run(call("create_pdf_radio_button", x_mm=20, y_mm=45, mode="interactive"))
    assert r.get("ok") is True


def test_1W4_create_pdf_combo_box(call):
    r = asyncio.run(
        call(
            "create_pdf_combo_box",
            x_mm=20,
            y_mm=55,
            width_mm=50,
            height_mm=6,
            options=["red", "green", "blue"],
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("name")


def test_1W5_create_pdf_list_box(call):
    r = asyncio.run(
        call(
            "create_pdf_list_box",
            x_mm=20,
            y_mm=65,
            width_mm=50,
            height_mm=20,
            options=["a", "b", "c"],
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1W6_create_pdf_push_button(call):
    r = asyncio.run(
        call(
            "create_pdf_push_button",
            x_mm=20,
            y_mm=90,
            width_mm=30,
            height_mm=8,
            label="Print",
            action_js="this.print();",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("name")


def test_1W7_create_uri_annotation(call):
    r = asyncio.run(
        call(
            "create_uri_annotation",
            uri="https://muxen.fr",
            frame_x_mm=20,
            frame_y_mm=110,
            frame_width_mm=40,
            frame_height_mm=6,
            link_text="muxen.fr",
            mode="interactive",
        )
    )
    assert r.get("ok") is True
    assert r.get("frame")
    assert r.get("created_frame") is True


def test_1W8_create_link_annotation(call):
    r = asyncio.run(
        call(
            "create_link_annotation",
            target_page=1,
            frame_x_mm=70,
            frame_y_mm=110,
            frame_width_mm=40,
            frame_height_mm=6,
            link_text="back to top",
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1W9_create_text_annotation(call):
    r = asyncio.run(
        call(
            "create_text_annotation",
            text="Reviewer note: looks good!",
            x_mm=180,
            y_mm=20,
            icon="comment",
            is_open=False,
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1W10_set_js_action(call):
    """Set a JS action on a previously-created text field."""
    f = asyncio.run(
        call(
            "create_pdf_text_field",
            x_mm=120,
            y_mm=130,
            width_mm=60,
            height_mm=8,
            mode="interactive",
        )
    )
    assert f.get("ok") is True
    name = f["name"]
    r = asyncio.run(
        call(
            "set_js_action",
            name=name,
            event="field_format",
            script="event.value = util.printf('%.2f', event.value);",
            mode="interactive",
        )
    )
    assert r.get("ok") is True


def test_1W11_js_action_validation(call):
    r = asyncio.run(
        call(
            "set_js_action",
            name="anything",
            event="bogus",
            script="x",
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "event must be one of" in r.get("error", "")


def test_1W12_text_annotation_icon_validation(call):
    r = asyncio.run(
        call(
            "create_text_annotation",
            text="x",
            x_mm=180,
            y_mm=200,
            icon="bogus",
            mode="interactive",
        )
    )
    assert r.get("ok") is False


# ----- Section 1.X — fonts -------------------------------------------------


def test_1X1_list_fonts(call):
    r = asyncio.run(call("list_fonts", mode="interactive"))
    assert r.get("ok") is True
    fonts = r.get("fonts") or []
    assert isinstance(fonts, list) and len(fonts) > 0


def test_1X2_list_fonts_detailed(call):
    r = asyncio.run(call("list_fonts_detailed", mode="interactive"))
    assert r.get("ok") is True
    fonts = r.get("fonts") or []
    assert fonts, "expected at least one font entry"
    sample = fonts[0]
    assert "family" in sample and "name" in sample and "filename" in sample


def test_1X3_list_monospace_fonts(call):
    r = asyncio.run(call("list_monospace_fonts", mode="interactive"))
    assert r.get("ok") is True
    monos = r.get("fonts") or []
    # Most systems carry at least one monospace face. If a CI environment
    # is absurdly bare we'll see zero — accept that, but in that case
    # `preferred` should be None.
    if monos:
        assert r.get("preferred") in monos


def test_1X4_font_is_available_true(call):
    fonts_r = asyncio.run(call("list_fonts", mode="interactive"))
    name = (fonts_r.get("fonts") or [None])[0]
    assert name, "no fonts to test against"
    r = asyncio.run(call("font_is_available", font=name, mode="interactive"))
    assert r.get("ok") is True and r.get("available") is True


def test_1X5_font_is_available_false(call):
    r = asyncio.run(call("font_is_available", font="DefinitelyNotAFont 9999", mode="interactive"))
    assert r.get("ok") is True and r.get("available") is False


def test_1X6_get_text_frame_font(call):
    f = asyncio.run(
        call(
            "create_text_frame",
            x_mm=20,
            y_mm=240,
            width_mm=40,
            height_mm=10,
            mode="interactive",
        )
    )
    name = f.get("name")
    assert name
    asyncio.run(call("set_text", name=name, text="hello", mode="interactive"))
    r = asyncio.run(call("get_text_frame_font", name=name, mode="interactive"))
    assert r.get("ok") is True
    assert isinstance(r.get("font"), str) and r["font"]


def test_1X7_list_extra_font_dirs(call):
    r = asyncio.run(call("list_extra_font_dirs"))
    # Either Scribus prefs is found (ok True with directories list) or not
    # found yet (ok False with explanatory error). Both are acceptable.
    assert "ok" in r
    if r.get("ok"):
        assert isinstance(r.get("directories"), list)
        assert r.get("prefs_xml")


def test_1X8_install_custom_font_missing_file(call):
    r = asyncio.run(call("install_custom_font", font_path="C:/does/not/exist/x.ttf"))
    assert r.get("ok") is False
    assert "not found" in (r.get("error") or "")


def test_1X9_install_custom_font_bad_extension(call, tmp_path):
    fake = tmp_path / "notafont.txt"
    fake.write_text("hello")
    r = asyncio.run(call("install_custom_font", font_path=str(fake)))
    assert r.get("ok") is False
    assert "unsupported font extension" in (r.get("error") or "")


# ----- Section 1.Y — code sample pattern -----------------------------------


def test_1Y1_create_code_sample_python(call):
    r = asyncio.run(
        call(
            "create_code_sample",
            code="def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n",
            language="python",
            x_mm=20,
            y_mm=20,
            width_mm=100,
            height_mm=40,
            mode="interactive",
        )
    )
    assert r.get("ok") is True, r.get("error")
    assert r.get("code")
    assert r.get("background")
    assert r.get("color_count") and r["color_count"] > 1


def test_1Y2_create_code_sample_with_title_and_lines(call):
    r = asyncio.run(
        call(
            "create_code_sample",
            code='import json\nprint(json.dumps({"a": 1}))\n',
            language="python",
            x_mm=20,
            y_mm=70,
            width_mm=120,
            height_mm=35,
            title="example.py",
            show_line_numbers=True,
            style="friendly",
            mode="interactive",
        )
    )
    assert r.get("ok") is True, r.get("error")
    assert r.get("title_bar") and r.get("title_text")
    assert r.get("line_count") == 2


def test_1Y3_create_code_sample_autodetect(call):
    r = asyncio.run(
        call(
            "create_code_sample",
            code='{"hello": "world", "n": 42}',
            x_mm=20,
            y_mm=110,
            width_mm=100,
            height_mm=20,
            mode="interactive",
        )
    )
    assert r.get("ok") is True, r.get("error")
    assert r.get("language")


def test_1Y4_unknown_pygments_style(call):
    r = asyncio.run(
        call(
            "create_code_sample",
            code="x = 1",
            language="python",
            x_mm=20,
            y_mm=140,
            width_mm=80,
            height_mm=15,
            style="not-a-style-xyz",
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "pygments style" in (r.get("error") or "")


def test_1Y5_unknown_pygments_lexer(call):
    r = asyncio.run(
        call(
            "create_code_sample",
            code="something",
            language="defnotalanguage",
            x_mm=20,
            y_mm=160,
            width_mm=80,
            height_mm=15,
            mode="interactive",
        )
    )
    assert r.get("ok") is False
    assert "pygments lexer" in (r.get("error") or "")


# ----- Section 1.N — markdown import ---------------------------------------


def test_1N1_import_markdown(call):
    md = "# Heading\n\nA paragraph.\n\n- one\n- two\n\n```python\ncode\n```\n"
    r = asyncio.run(
        call(
            "import_markdown", markdown_text=md, x_mm=20, y_mm=200, width_mm=170, mode="interactive"
        )
    )
    assert r.get("ok") is True


# ----- Section 1.O — resources ---------------------------------------------


def test_1O1_resource_document_info(mcp):
    out = asyncio.run(mcp.read_resource("scribus://document/info"))
    text = out[0].content if isinstance(out, list) and out else str(out)
    info = json.loads(text) if isinstance(text, str) else text
    assert info.get("has_doc") in (True, False)


def test_1O3_resource_colors(mcp):
    out = asyncio.run(mcp.read_resource("scribus://document/colors"))
    text = out[0].content if isinstance(out, list) and out else str(out)
    data = json.loads(text) if isinstance(text, str) else text
    assert isinstance(data, list) and "Black" in data


def test_1O4_resource_fonts(mcp):
    out = asyncio.run(mcp.read_resource("scribus://document/fonts"))
    text = out[0].content if isinstance(out, list) and out else str(out)
    data = json.loads(text) if isinstance(text, str) else text
    assert "available" in data


# ----- Section 1.P — prompts -----------------------------------------------


def test_1P1_manual_from_markdown_prompt(mcp):
    msgs = asyncio.run(mcp.get_prompt("manual_from_markdown", {"markdown_path": "x.md"}))
    assert msgs is not None


def test_1P2_data_merge_csv_prompt(mcp):
    msgs = asyncio.run(
        mcp.get_prompt("data_merge_csv", {"template_sla": "t.sla", "csv_path": "d.csv"})
    )
    assert msgs is not None


# ----- Section 1.R — error paths -------------------------------------------


def test_1R2_bad_frame_name(call):
    r = asyncio.run(call("get_text", name="ThisFrameDoesNotExist", mode="interactive"))
    assert r.get("ok") is False or "error" in r or r.get("text") in (None, "")


# ----- Cleanup -------------------------------------------------------------


def test_zzz_close_document(call):
    """Runs last alphabetically — leaves Scribus clean."""
    r = asyncio.run(call("close_document", mode="interactive"))
    assert r.get("ok") is True

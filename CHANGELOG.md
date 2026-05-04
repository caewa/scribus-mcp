# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-04

First public PyPI release. The MCP server has been driving Scribus end-to-end
on Windows 11 + Scribus 1.7.3 and Debian 13 + Scribus 1.6.3 throughout
development; the cumulative test suite is **198 passing / 2 conditional
skips** (55 unit + 132/134 Phase 1 interactive + 11 Phase 2 headless on
Linux, 125/125 + 8/8 on Windows).

### Added

#### Tool surface (~125 MCP tools across 17 modules)

- **Document lifecycle.** `create_document`, `open_document`, `save_document`,
  `save_document_as`, `close_document`, `get_document_info`,
  `set_document_metadata`.
- **Pages.** `add_page`, `delete_page`, `goto_page`, `get_page_count`,
  `apply_master_page`, `list_master_pages`, `create_master_page`.
- **Frames + primitives.** `create_text_frame`, `create_image_frame`,
  `create_rectangle`, `create_ellipse`, `create_line`, `create_polygon`,
  `create_polyline`, `create_bezier_line`, `create_path_text`,
  `delete_object`, `move_object`, `resize_object`, `list_page_objects`,
  `group_objects`.
- **Text content + flow.** `set_text`, `append_text`, `get_text`,
  `get_visible_text`, `link_text_frames`, `is_text_overflowing`.
- **Text formatting.** `set_font`, `set_font_size` (+ `_pt` variant),
  `set_text_color`, `set_text_alignment`, `set_text_vertical_alignment`,
  `set_line_spacing`. The `_pt` variants accept the 1/100-pt integers
  Scripter expects directly, for callers that prefer not to multiply by 100.
- **Styles.** `list_paragraph_styles`, `list_character_styles`,
  `apply_paragraph_style`, `apply_character_style`,
  `import_styles_from_file`.
- **Object styling.** `set_fill_color`, `set_line_color`, `set_fill_shade`,
  `set_line_shade`, `set_fill_transparency`, `set_line_transparency`,
  `set_line_width`, `set_line_style`, `set_line_cap`, `set_line_join`,
  `set_corner_radius`, `apply_gradient` (linear + radial, 2-stop),
  `clear_gradient`, plus matching getters.
- **Colors.** `define_color_cmyk`, `define_color_rgb`, `list_colors`,
  `delete_color`.
- **Images.** `load_image`, `set_image_scale`, `scale_image_to_frame`,
  `set_image_offset`.
- **Layers.** `create_layer`, `delete_layer`, `list_layers`,
  `set_active_layer`, `send_to_layer`, `set_layer_visible`,
  `set_layer_printable`.
- **Search.** `find_and_replace_text`, `find_objects`.
- **Fonts.** `list_fonts`, `list_fonts_detailed`, `list_monospace_fonts`,
  `font_is_available`, `get_text_frame_font`, `install_custom_font` (copies
  to a managed dir + patches Scribus prefs `ExtraFontDirs`),
  `list_extra_font_dirs`.
- **Export.** `export_pdf`, `render_page_to_image` (returns inline base64
  PNG), `preflight_check`.
- **PDF interactivity.** `create_pdf_text_field`, `create_pdf_checkbox`,
  `create_pdf_radio_button`, `create_pdf_combo_box`, `create_pdf_list_box`,
  `create_pdf_push_button`, `create_link_annotation`,
  `create_uri_annotation`, `create_file_annotation`,
  `create_text_annotation`, `set_js_action`, `get_js_action`,
  `is_annotated`.
- **High-level patterns** (one call → composed multi-element output):
  `create_radar_chart`, `create_bar_chart`, `create_pie_chart`,
  `create_timeline`, `create_callout_box`, `create_kpi_tile`,
  `create_comparison_table`, `create_qr_code_block`, `create_dot_label`,
  `create_numbered_badge`, `create_code_sample` (Pygments-tokenized,
  monospace auto-pick).
- **Region-shaped layouts.** `create_two_column_text`,
  `create_text_with_image`, `create_section_header`, `create_hero_band`,
  `create_numbered_steps`, `create_image_caption`,
  `create_table_of_contents`, `create_sidebar_layout`, `create_kpi_row`,
  `create_equal_columns`, `create_card_grid`.
- **Markdown bridge.** `import_markdown` walks inline tokens, strips
  `**` / `*` / `` ` `` markers, and re-applies bold / italic / monospace
  via `selectText` + `setFont` (auto-discovers the variant of the frame's
  font family).

#### Backends + transports

- **Headless backend** — fires a fresh `scribus -g -ns -py …` per call.
  Best for batch jobs (CI manual generation, data merges).
- **Interactive backend** — TCP-loopback bridge running inside an open
  Scribus window, driven by a `.spy` script that dispatches MCP calls
  onto Scribus's Qt main thread via a `QTimer`. Survives across calls,
  fast IPC, document state persists, the user can watch (or take over)
  the work in real time.
- **Auto backend selection.** `mode="auto"` (the default for every tool)
  prefers the interactive bridge when one is reachable, otherwise falls
  back to headless.
- **Auto-launch.** Tool calls with `mode="interactive"` will spawn Scribus
  and load the bridge for you if no bridge is reachable. Idempotent — if
  one's already up, returns immediately.
- **Scribus 1.6 + 1.7 dual support.** The auto-launcher probes
  `scribus -v` (locale-tolerant) and only emits the `-cl` console-only
  flag on 1.7+; on 1.6 it falls back to the flags 1.6 actually accepts.
- **Both stdio and Streamable HTTP transports.** Use HTTP for long-running
  headless jobs — it streams progress updates in real time, where stdio
  would block.
- **Resources** (4) exposing read-only document state:
  `scribus://document/info`, `…/colors`, `…/fonts`,
  `…/missing-resources`.
- **Prompts** (3): `best_practices` (the LLM rule sheet, also shipped as
  `doc/BEST_PRACTICES.md`), `manual_from_markdown`, `data_merge_csv`.
- **Gated `run_script` escape hatch** for arbitrary Scripter Python.
  Disabled by default, opt-in via `--enable-run-script` /
  `SCRIBUS_MCP_RUN_SCRIPT=1`.

#### Runtime version gating (MCP-client feedback contract)

Tools that wrap Scripter calls only present on Scribus 1.7+ now return a
structured payload on 1.6 instead of leaking a raw `AttributeError`:

```json
{
  "ok": false,
  "error": "create_qr_code_block (scribus.createBarcode) requires Scribus 1.7.0+ (this Scribus reports 1.6.3). ...",
  "required_version": "1.7.0",
  "actual_version": "1.6.3"
}
```

`required_version` and `actual_version` are stable fields the MCP client
can pattern-match on. The version probe runs once per backend instance
(cached via `scribus.scribus_version_info`), so the floor check is free
on subsequent calls. Currently only `create_qr_code_block` is gated;
[doc/SUPPORT.md](doc/SUPPORT.md) tracks the matrix.

#### Opt-in Scribus AppImage auto-fetch (Linux)

Distros that only ship Scribus 1.6 (Debian 13, Ubuntu 24.04, …) can pull
the official 1.7.x AppImage on demand:

- `scribus-mcp --fetch-appimage` — explicit one-shot install. Lands at
  `~/Applications/Scribus-X.Y.Z-x86_64.AppImage`, which the launcher
  already probes.
- `SCRIBUS_MCP_AUTO_APPIMAGE=1` — lazy: launcher fetches on first call
  when no Scribus binary is resolvable. Off by default (~140 MB).

CLI flags + `SCRIBUS_MCP_APPIMAGE_*` env vars override URL, version,
SHA256 pin, and install dir. Upstream doesn't publish SHA256 alongside
the AppImage; default path verifies via TLS + a 50 MB sanity floor, with
optional user-supplied SHA256 pinning.

#### Helper scripts

- `scripts/disable-startup-dialog-windows.ps1` — flips
  `ShowStartupDialog="0"` in `scribusXYZ.rc` so the New Document wizard
  stops blocking `-py` script execution.
- `scripts/disable-startup-dialog-linux.sh` — Linux equivalent (was
  flagged TBD in the README).
- `scripts/install-pyqt-windows.ps1` — auto-detects Scribus's bundled Qt
  version and installs the matching `PyQt6==<MAJOR>.<MINOR>.*` so the
  bridge's Qt binding ABI matches.
- `scripts/demo-explainer.py`, `scripts/demo-showcase.py` — end-to-end
  demos exercising every category of tool the MCP exposes.

#### Caller-side Python helper

- `from scribus_mcp.layout import PageCursor` — tracks the running y for
  a column so multi-band scripts declare a sequence of bands instead of
  hand-coding y. Methods: `band(height_mm)`, `split([widths], height_mm)`,
  `jump_to(y_mm)`, etc.

#### Configuration knobs

All env vars are optional:

- `SCRIBUS_BIN` — path to Scribus executable (auto-detected; resolves
  bare command names via `$PATH`).
- `SCRIBUS_MCP_RUN_SCRIPT` — set to `1` to register the `run_script`
  tool.
- `SCRIBUS_MCP_USE_XVFB` — set to `1` to wrap headless invocations in
  `xvfb-run -a`.
- `SCRIBUS_MCP_LOG_LEVEL` — Python log level (default `INFO`).
- `SCRIBUS_MCP_EXTRA_FONT_PATHS` — `os.pathsep`-separated dirs to
  register as Scribus *Additional Font Paths* per headless spawn.
- `SCRIBUS_MCP_AUTO_APPIMAGE` — opt-in Linux AppImage auto-fetch.
- `SCRIBUS_MCP_APPIMAGE_{URL,VERSION,SHA256,INSTALL_DIR}` — override
  knobs for the AppImage fetch.

### Fixed

- **Bridge response buffer.** `asyncio.StreamReader`'s default 64 KiB
  cap truncated `list_fonts*` and `scribus://document/fonts` responses
  on systems with many fonts. Bumped to 16 MiB on `open_connection`.
- **Auto-launch dup-window guard.** The "is Scribus already running?"
  check used `pgrep -f scribus` (matches full command line), which
  spuriously matched any process whose argv contained "scribus" — e.g.
  pytest running from a `scribus-mcp/` checkout. Now uses `pgrep -x`
  (exact name match).
- **Wheel build.** `[tool.hatch.build.targets.wheel.force-include]`
  referenced `doc/BEST_PRACTICES.md`, but the sdist didn't carry `doc/`,
  so `uv build` failed at the wheel-from-sdist step.

### Notes

- **Scribus 1.6 vs 1.7.** The MCP works on both. Distros that ship only
  1.6 (Debian 13, Ubuntu 24.04) get the `create_qr_code_block` tool
  gated off; everything else (~140 Scripter functions) works
  identically. See [doc/SUPPORT.md](doc/SUPPORT.md) for the matrix and
  README's *Scribus version requirements per feature* for the
  per-tool minimums.
- **Linux first-run.** Scribus's "New Document" wizard blocks `-py`
  execution until dismissed. Run Scribus once manually, then
  `./scripts/disable-startup-dialog-linux.sh --force` to write
  `ShowStartupDialog="0"` into `~/.config/scribus/scribusXYZ.rc`.

[1.0.0]: https://github.com/caewa/scribus-mcp/releases/tag/v1.0.0

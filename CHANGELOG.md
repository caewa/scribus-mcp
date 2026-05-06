# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] — 2026-05-06

Bridge gains a third dispatch path that drops the bundled-PyQt6
dependency entirely when running against a Scribus build that exposes
the new Scripter primitives `scribus.invokeLater(callable, *args)` and
`scribus.processEvents()`. Includes the upstream Scribus patch
(`scripter-invokelater.patch`) at the repo root for reference.

### Added

- **Native Scripter dispatch path in
  [src/scribus_mcp/bridge/scribus_mcp_bridge.spy](src/scribus_mcp/bridge/scribus_mcp_bridge.spy).**
  Bridge probes `hasattr(scribus, "invokeLater")` at startup and
  prefers the native primitives over the legacy PyQt6 `QTimer` path.
  Selection order: native invokeLater → PyQt6 QTimer → main-thread
  blocker. Startup log now reports `dispatch=native-invokeLater |
  qt-PyQt6 | main-thread-blocking`. With the patched build there is
  no Python Qt binding to install — the bundled-PyQt6 step (whose
  Qt minor had to match Scribus's exactly, fragile on Windows) is no
  longer needed.
- **[scripter-invokelater.patch](scripter-invokelater.patch)** at the
  repo root: small upstream Scribus patch (+87 lines, 3 files in
  `scribus/plugins/scriptplugin/`) adding `scribus.invokeLater` and
  `scribus.processEvents`. Apply with
  `git apply ../scripter-invokelater.patch` from inside a Scribus
  source checkout, then rebuild.

### Changed

- **`_block_main_thread_dispatch` pumps Qt via
  `scribus.processEvents()` when available**, falling back to the
  historical `scribus.progressReset()` side-effect on unpatched
  builds. The blocker is now also entered in GUI mode under the
  native path: Scribus's `PyRun_String` keeps the GIL on the main
  thread, so a returning script would leave the listener thread
  starving on GIL re-acquisition after every `accept()`. The
  blocker's `_inbox.get(timeout=…)` and `time.sleep` release the
  GIL periodically so the listener can post `invokeLater` events.
  PyQt manages those transitions internally, so the QTimer path
  still returns immediately.

### Fixed

- Three pre-existing ruff findings cleaned up:
  `[x] + list(y)` → iterable unpacking
  ([table_of_contents.py](src/scribus_mcp/tools/layouts/table_of_contents.py),
  [timeline.py](src/scribus_mcp/tools/patterns/timeline.py)) and a
  `if/else` collapsed to a ternary in `timeline.py`. `ruff check
  src/` now passes cleanly.

## [1.2.0] — 2026-05-06

Two cooperating features in this minor: every multi-element pattern
and layout now bundles its outputs into a Scribus group, and
`create_timeline(label_rows>=2)` switches from "stack above" to
"alternate above/below the axis" so manual document editing stays
ergonomic.

### Added

- **Every pattern/layout returns a `"group"` field** naming a Scribus
  group that owns axis, markers, connectors, labels, dates, cards,
  cells, etc. — whatever the feature emits. Selecting the group in the
  Scribus GUI moves, scales or deletes the whole feature as a single
  unit instead of having to marquee-select each piece. Implemented via
  the new shared helper
  [src/scribus_mcp/tools/patterns/_grouping.py](src/scribus_mcp/tools/patterns/_grouping.py),
  applied to 13 patterns (`timeline`, `bar_chart`, `pie_chart`,
  `radar_chart`, `comparison_table`, `callout_box`, `code_sample`,
  `axes_strip`, `pillar_strip`, `highlight_card_row`, `dark_kpi_band`,
  `dot_label` × 2, `kpi_tile`, `qr_code_block`) and 11 layouts
  (`kpi_row`, `card_grid`, `numbered_steps`, `equal_columns`,
  `hero_band`, `image_caption`, `section_header`, `sidebar_layout`,
  `table_of_contents`, `text_with_image`, `two_column_text`).
- **TL;DR install snippet now sets `SCRIBUS_MCP_IGNORE_HOST_SCRIBUS=1`**
  alongside `SCRIBUS_MCP_AUTO_APPIMAGE=1`, so distros shipping an
  older Scribus 1.6 still get the 1.7.x AppImage path on first run
  ([README.md](README.md)).

### Changed

- **`create_timeline(label_rows>=2)` now alternates above/below the
  axis** instead of stacking extra rows above. Even rows (0, 2, …)
  sit above the axis, odd rows (1, 3, …) below. Dates render close to
  the axis on the same side as their item's label (between label and
  axis); when any item carries a date, the label distance auto-bumps
  to clear the date row. Bbox now extends both above and below the
  axis. `label_rows=1` keeps the legacy single-row layout untouched
  ([src/scribus_mcp/tools/patterns/timeline.py](src/scribus_mcp/tools/patterns/timeline.py)).
- **`label_rows` accepts numeric strings** (`"2"`, `"3"`, …) in
  addition to ints and `"auto"`, since the MCP boundary serialises
  ints to strings.

### Notes

- 151 unit tests pass (was 144; +7 reflecting the new alternating
  layout assertions and the no-overwrite-of-`last_body` mock contract
  used by patterns/layouts that issue a trailing `groupObjects` call).

[1.2.0]: https://github.com/caewa/scribus-mcp/releases/tag/v1.2.0

## [1.1.4] — 2026-05-05

Two follow-ups to 1.1.3 driven by a fresh end-to-end test against the
Scribus 1.7.3 AppImage:

### Fixed

- **AppImage window stayed black until a tool call.** When PyQt isn't
  installed in the running Scribus's Python (the case for the
  bundled-everything 1.7.3 AppImage), the bridge falls back to a
  blocking dispatch loop that holds the main thread — Qt's event loop
  never gets a chance to paint, so the main window appeared black
  until a Scripter call yielded mid-tick. The bridge now calls
  ``scribus.progressReset()`` on each idle cycle (every 100 ms),
  which internally calls ``QApplication::processEvents()`` so Qt
  flushes its paint + input queue. Side effect: the progress bar is
  reset to 0 ~10×/sec, which is invisible during normal operation.
  ([src/scribus_mcp/bridge/scribus_mcp_bridge.spy](src/scribus_mcp/bridge/scribus_mcp_bridge.spy))

### Added

- **`create_timeline(label_rows="auto" | int)`** ([src/scribus_mcp/tools/patterns/timeline.py](src/scribus_mcp/tools/patterns/timeline.py)).
  Adjacent items can stagger across N stacked y-rows so each label
  competes only with the same-row neighbour ``label_rows`` markers
  away — roughly ``label_rows×`` more horizontal slot per label. The
  new ``"auto"`` default estimates each label's rendered width from
  its character count and the font size; if any label overflows its
  single-row slot, the timeline bumps to 2 rows automatically.
  Callers can override with an explicit ``int`` (1..4) — pass
  ``label_rows=1`` to force a single line and accept the truncation,
  or ``label_rows=3`` for very dense timelines. The result dict
  surfaces ``label_rows`` so callers can see whether auto bumped.
  Fixes the "v1.0 — first rLeolenags-teerm support"-style collisions
  in the "A DECADE OF RELEASES" timeline.

### Notes

- 128 unit tests pass (was 119; +9 in `tests/test_timeline_label_rows.py`
  covering the row layout, same-row neighbour width bounding, the
  bbox grow, the auto-detect short-vs-long label paths, and explicit
  override + validation).

[1.1.4]: https://github.com/caewa/scribus-mcp/releases/tag/v1.1.4

## [1.1.3] — 2026-05-05

Bug-fix: 1.1.2's AppImage wiring works (Scribus 1.7.3 actually
launches), but two follow-ups surfaced once a 1.7.x window was on
screen — the window painted black on Wayland and `get_scribus_version`
still reported 0.0.0.

### Fixed

- **Black AppImage window on Wayland.** The 1.7.3 AppImage's bundled
  Qt doesn't handle Wayland cleanly — the main window came up but
  rendered all-black. The launcher now sets `QT_QPA_PLATFORM=xcb` in
  the spawn env (via `setdefault`, so a user-set value still wins) so
  Qt picks the X11 backend it actually works under.
- **`-cl` flag dropped from the bridge spawn cmd.** Scribus 1.7.3's
  `--help` doesn't list `-cl` — the launcher was emitting it for 1.7+
  thinking it was a "console-only" feature flag, but it's silently
  ignored on every 1.7.x build we've tested. The matching test pins
  the new "never emit" behaviour.
- **`get_scribus_version` returned 0.0.0 against 1.7.3.** The probe
  read `scribus.scribus_version_info`, which the 1.7.3 AppImage
  doesn't expose as a top-level attribute. Added a fallback that
  splits the dotted string in `scribus.scribus_version` ("1.7.3" →
  `(1, 7, 3)`).

### Notes

- 119 unit tests pass (was 116; +3 covering the dropped flag, the
  Linux env tweak, and the user-override-wins behaviour).

[1.1.3]: https://github.com/caewa/scribus-mcp/releases/tag/v1.1.3

## [1.1.2] — 2026-05-05

Bug-fix: 1.1.1 wired `SCRIBUS_MCP_IGNORE_HOST_SCRIBUS` into the bridge
launcher only — the headless backend kept using the host binary, so
`mode="auto"` (the default) still spawned host Scribus 1.6.3 even when
the user had asked for the AppImage. Visible symptom: calling
`get_scribus_version` returned 1.6.3 with both `IGNORE_HOST_SCRIBUS=1`
and `AUTO_APPIMAGE=1` set.

### Fixed

- **Headless backend now honours `SCRIBUS_MCP_IGNORE_HOST_SCRIBUS` /
  `SCRIBUS_MCP_AUTO_APPIMAGE`.** Both backends now route through a
  single `resolve_scribus_binary(config)` helper in
  [src/scribus_mcp/backends/_launcher.py](src/scribus_mcp/backends/_launcher.py)
  that consults the env vars and caches the resolved path per
  `Config` instance — so the AppImage download only happens once even
  when headless respawns Scribus per tool call.

### Notes

- 116 unit tests pass (was 113; +3 covering the shared resolver,
  caching, and the headless-uses-AppImage regression).

[1.1.2]: https://github.com/caewa/scribus-mcp/releases/tag/v1.1.2

## [1.1.1] — 2026-05-05

Small follow-up to 1.1.0 — adds a knob the launcher was missing for
hosts that have Scribus 1.6 installed but want the 1.7.x AppImage.

### Added

- **`SCRIBUS_MCP_IGNORE_HOST_SCRIBUS=1`** ([src/scribus_mcp/config.py](src/scribus_mcp/config.py),
  [src/scribus_mcp/backends/_launcher.py](src/scribus_mcp/backends/_launcher.py))
  skips every host-binary lookup (`SCRIBUS_BIN`, `$PATH`, the
  well-known install paths, the AppImage glob in `~/Applications/`)
  and forces the AppImage path. Pair with `SCRIBUS_MCP_AUTO_APPIMAGE=1`.
  Use case: distro ships Scribus 1.6 (Debian 13, Ubuntu 24.04) but the
  user wants 1.7.x for the full feature surface
  (`create_qr_code_block`, …) — without IGNORE_HOST, the host 1.6
  always wins because `_resolve_scribus_bin` finds it on `$PATH`
  before AUTO_APPIMAGE kicks in.

### Fixed

- Setting IGNORE_HOST without AUTO_APPIMAGE now reports the
  configuration error directly ("set AUTO_APPIMAGE or unset
  IGNORE_HOST") instead of the ambiguous "binary not found at ..."
  message.

### Notes

- 113 unit tests pass (was 110; +3 for the new env var → Config wiring,
  the resolve-skipped path, and the misconfiguration error).

[1.1.1]: https://github.com/caewa/scribus-mcp/releases/tag/v1.1.1

## [1.1.0] — 2026-05-05

Driven by issues seen in a follow-up LLM-produced brief on top of 1.0.1.
Adds a document-wide palette layer + several quality-of-life fixes
across the high-traffic patterns. Backwards-compatible: scripts that
pass explicit colors are unaffected; the changed defaults only matter
when a script *omitted* the color argument and didn't define the
canonical palette role names.

### Added

- **Palette roles** ([src/scribus_mcp/tools/palette.py](src/scribus_mcp/tools/palette.py)).
  Every color slot in patterns + layouts now defaults to one of the
  canonical role names — `primary`, `accent`, `surface`, `ink`,
  `muted`, `warning`, `success`, `subtle`. Define those names with
  `define_color_rgb` / `define_color_cmyk` once and every later
  `create_card_grid`, `create_callout_box`, `create_kpi_tile`,
  `create_section_header`, `create_hero_band`, `create_timeline`,
  `create_comparison_table`, `create_radar_chart`, `create_bar_chart`,
  `create_pie_chart`, `create_numbered_steps`, `create_sidebar_layout`,
  `create_table_of_contents`, etc. inherits the palette without
  restating the color on every call. Per-call literals still win —
  pass `accent_color="Brand Coral"` to override one slot.
  Documented in
  [doc/BEST_PRACTICES.md#palette-roles](doc/BEST_PRACTICES.md#palette-roles--define-once-every-tool-uses-them).
- **`list_palette_roles` tool** lists the canonical role names so the
  LLM can introspect the contract before defining colors.
- **`get_scribus_version` tool** ([src/scribus_mcp/tools/document.py](src/scribus_mcp/tools/document.py))
  returns `{major, minor, patch, version, version_string,
  is_17_or_newer}`. The internal version probe drove version-gated
  features (`create_qr_code_block` requires 1.7+) but was never
  exposed to the MCP client; LLMs can now branch their workflow on
  the running Scribus's capabilities up front.
- **Shape primitives accept fill / line styling at creation time.**
  `create_rectangle`, `create_ellipse`, `create_line`,
  `create_polygon`, `create_polyline`, `create_bezier_line` gained
  `fill_color`, `fill_shade`, `line_color`, `line_width_pt` (palette
  roles accepted). `line_color="None"` suppresses the default 1pt
  black stroke; omitting the args keeps the previous create-only
  behaviour. Closes the silent-arg-drop bug where an LLM passed
  `fill_color="Brand"`, got `ok: true` back, and the shape rendered
  with PCOLOR="Black" because the kwarg wasn't declared on the tool.
  ([src/scribus_mcp/tools/shapes.py](src/scribus_mcp/tools/shapes.py))
- **`create_document(pages: int = 1)`** is now honored (1..1000 range).
  The parameter was always plumbed through to Scripter's `newDocument`
  but never declared on the tool, so calls like
  `create_document(pages=5)` returned `ok: true` with a 1-page doc.
- **Per-backend palette cache** with seed-on-define + invalidate-on-
  document-lifecycle hooks. `getColorNames` is probed at most once per
  pattern call; the cache absorbs every later
  `define_color_rgb` / `define_color_cmyk` and is dropped on
  `create_document` / `open_document` / `close_document` /
  `revert_document` / `delete_color`.

### Fixed

- **`create_kpi_tile` still wrapped `"Apache 2.0"` onto two lines.**
  The 1.0.1 horizontal-fit pass used a 0.55 average-glyph-advance
  estimate; DejaVu Sans (the Scribus default) is closer to 0.56 for
  mixed text and noticeably wider for capital-leading words. Bumped
  the factor to 0.62 with a 0.93 safety multiplier on the inner width
  — covers DejaVu and every common sans-serif we ship without forcing
  further shrink on short numeric values like `"15.2k"` / `"177"`.
- **`create_timeline` labels collided when items were unevenly
  spaced.** The previous implementation used a single uniform slot
  width derived from `width_mm / (n - 1)`; on a release-history
  timeline where 2025 sat one year before 2026 next to a three-year
  gap from 2016→2019, the `"v4.x cycle"` and `"today"` labels overran
  each other. Per-label width is now bounded by the distance to each
  neighbour, so labels stay separated regardless of `position`
  distribution.
- **`create_timeline` reported a bbox flush against the date row.**
  The returned `bbox` ended exactly at the bottom of the date frames,
  so callers chaining via `PageCursor` placed the next band (or the
  page footer) right against the dates. New `bottom_margin_mm`
  parameter (default 3 mm) reserves visual breathing room in the
  reported bbox.
- **`create_section_header` accent rule sat too far below the title.**
  Default `title_height_mm` (9 mm) over-reserved descender room for
  the 16 pt title and `rule_offset_mm` (1 mm) added another mm on top
  — produced a ~4 mm visible gap between baseline and rule that read
  as a detached underline. Tightened defaults to 7 mm / 0.5 mm so the
  rule hugs the title; callers can still pass larger values for an
  airy layout.

### Changed

- **`auto_height` now defaults to `True` on `create_card_grid` and
  `create_callout_box`.** The 1.0.1 release shipped the feature but
  kept the default `False`, so the same brief still produced cards
  either overflowing (4-up grid where bodies were too long for the
  fixed cell) or trailing a tall whitespace gap (3-up / 2-up grid
  where bodies were shorter than the fixed cell). Cards now adapt to
  their content by default; pass `auto_height=False` only when you
  specifically want the caller-provided `height_mm` honoured verbatim.
- **Color slot defaults flip from `"Black"` to role names.** Slots
  that conventionally tinted Black (`fill_shade=8` for cards,
  `fill_shade=12` for KPIs, `axis_shade=50` for timelines, etc.) keep
  that conventional shade *only when the role is undefined*. When the
  role resolves, tools draw at full shade so the LLM sees the exact
  hue it defined. Caller-provided shades always win — pass
  `fill_shade=20` to override either path.
- **Shade parameters now take `int | None`** as their type — `None`
  is the new "let the resolver decide" sentinel; an explicit int still
  pins the shade.

### Documentation

- New "Palette roles — define once, every tool uses them" section in
  [doc/BEST_PRACTICES.md](doc/BEST_PRACTICES.md), with the role table,
  a typical opener snippet, and a callout for the common pitfall of
  defining custom color names (`ZephyrPurple`) instead of the
  canonical roles (silently makes every tool with an omitted color
  argument fall back to Black).
- README: new "Wire Claude Code at a local checkout" sub-section under
  Dev mode for testing local branches via `uvx --from <path>`. (Also
  fixes the easy-to-miss trailing `scribus-mcp` arg the line
  continuation had hidden.)

### Notes

- 110 unit tests pass (was 88; +22 across `tests/test_palette.py`,
  `tests/test_shape_styling.py`, plus 3 in `tests/test_version_gate.py`
  for the new MCP tool).
- 6 new Phase 1 (live) regression tests in `tests/test_phase1_interactive.py`
  section 1.SR — round-trip-through-save_document, asserting
  `PCOLOR="Brand"` actually lands in the saved SLA for each affected
  shape primitive. Gated by `SCRIBUS_MCP_LIVE=1`.
- Ruff clean across `src/` and `tests/`.

[1.1.0]: https://github.com/caewa/scribus-mcp/releases/tag/v1.1.0

## [1.0.1] — 2026-05-04

Bug-fix release driven by issues seen in real LLM-produced documents.
No tool removals or breaking changes.

### Added

- **`auto_height=True` on `create_callout_box` and `create_card_grid`.**
  After `setText` the tool runs Scribus's `layoutText` /
  `textOverflows` to find the smallest non-truncating body height and
  resizes the body frame, the background rect, and (for cards) the
  accent stripe to fit. For `card_grid`, every card in a row adopts
  that row's tallest fitted height so the row stays visually uniform,
  and rows below are repacked upward to remove the gap. Returns the
  fitted `height_mm` / `grid_height_mm` for chaining via
  `PageCursor.jump_to(...)`. Fixes the cards-with-short-body whitespace
  problem the cards in the "Security model" section exhibited.
  ([src/scribus_mcp/tools/_fit.py](src/scribus_mcp/tools/_fit.py),
  [doc/BEST_PRACTICES.md](doc/BEST_PRACTICES.md#cards-with-short-body-text--auto_heighttrue))
- **`clean_user_text` boundary helper** in
  [src/scribus_mcp/tools/_common.py](src/scribus_mcp/tools/_common.py) —
  defensive `html.unescape` applied at every user-text `setText` call
  site, so an LLM that pre-encodes `&` as `&amp;` (or `<` as `&lt;`,
  etc.) doesn't leak the encoded form into the rendered PDF. Single-
  pass: `&amp;amp;` → `&amp;` (intent preserved). `&nbsp;` decodes to
  U+00A0, so `"Apache&nbsp;2.0"` keeps the version glued to the name.
  Skipped for `create_code_sample` (code may legitimately contain
  literal entities) and `find_and_replace_text` (search patterns).
- **`CHANGELOG.md`** (this file). Earlier 1.0.0 work is back-filled.
- **Test CI workflow** ([.github/workflows/test.yml](.github/workflows/test.yml))
  running unit tests on Linux + macOS + Windows × Python 3.11 / 3.12 /
  3.13, plus `ruff check`, `uv build`, `twine check`, and a fresh-venv
  wheel-install smoke test. The publish workflow already existed; this
  is the matching gate on PRs and pushes to `main`.
- **`doc/BEST_PRACTICES.md`** — three new rules an LLM driving the MCP
  should follow:
  - Pass plain text; never HTML-escape (covers the `clean_user_text`
    contract above).
  - Use two frames for left+right page chrome; don't pad with spaces.
    Documents the `"…rtos                            page 3 / 5"`
    anti-pattern that produces ragged-right footers per page.
  - Use `auto_height=True` for cards with variable-length body text.

### Fixed

- **HTML entities rendered as literal characters in produced PDFs.**
  LLM clients sometimes pre-encode user text (`"AT&amp;T"`,
  `"OVERVIEW &AMP; KERNEL FEATURES"`, `"Kernel &amp;amp; runtime"`),
  treating it as if it were destined for HTML. Scribus stored those
  strings verbatim, then re-XML-escaped on save, so the rendered PDF
  showed the literal characters. The boundary decode (above) cures it
  at every user-text `setText` callsite — `set_text` / `append_text`,
  every pattern's `title` / `caption` / `label` / `body`, every
  layout's `title` / `eyebrow` / `subtitle` / `right_text`, form
  `default_value` / `label`, annotation `link_text`, etc.
- **KPI tile values overflowing horizontally and wrapping to two
  lines.** `create_kpi_tile` previously only auto-shrunk the value
  font on vertical fit; long values like `"Apache 2.0"` at 22 pt in a
  ~33 mm-wide tile rendered over two lines because the horizontal axis
  wasn't checked. Added a horizontal-fit pass that takes the smaller
  of vertical and horizontal max font sizes, with a 6 pt minimum
  floor.
- **Wheel build failure (`Forced include not found:
  doc/BEST_PRACTICES.md`).** `uv build` rolls a sdist first then
  builds the wheel from inside the unpacked sdist, but
  `[tool.hatch.build].include` only listed `src/**` paths so `doc/`
  was missing in the sdist phase. Added an explicit
  `[tool.hatch.build.targets.sdist].include` listing pulling in the
  doc file plus `LICENSE` and `README.md`.
- **Test CI install step couldn't find a Python interpreter.** First
  run of `test.yml` had every job failing at `uv pip install --system
  -e ".[dev]"` because PEP 668's `EXTERNALLY-MANAGED` marker on Ubuntu
  24.04's system Python rejects `--system`, and `setup-uv@v5`'s
  managed Python isn't on `$PATH`. Switched to `uv sync --extra dev`
  + `uv run <tool>` (the canonical Astral pattern).
- **Windows test job failure.** `tests/test_appimage.py` asserted
  `(stat.st_mode & 0o777) == 0o755` after `Path.chmod(0o755)`. Windows
  `chmod` is a near-noop for POSIX bits; the AppImage feature is
  Linux-only anyway. Gated the assertion behind `sys.platform !=
  "win32"`.

### Notes

- 88 unit tests pass (was 52 in 1.0.0; +36 new across `clean_user_text`,
  `kpi_tile_autofit`, `appimage`, `version_gate`, `launcher`).
- Ruff clean across `src/` and `tests/`.
- Live Phase 1 still 132 / 134 on Linux + Scribus 1.6.3 (unchanged from
  1.0.0).

[1.0.1]: https://github.com/caewa/scribus-mcp/releases/tag/v1.0.1

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

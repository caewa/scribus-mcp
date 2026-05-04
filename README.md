# scribus-mcp

An MCP (Model Context Protocol) server that lets Claude drive [Scribus](https://www.scribus.net/) — the open-source desktop publishing app — through its Python Scripter API.

Two backends behind one tool surface:

- **Headless** — fires a fresh `scribus -g -py …` per call. Best for batch jobs (CI manual generation, data merges).
- **Interactive** — talks over TCP loopback to a small `.spy` bridge running inside an open Scribus window. Best for assisting on a document you already have open.

`mode="auto"` (the default for every tool) prefers the interactive bridge when one is reachable, otherwise falls back to headless.

## Status

Validated end-to-end on:

| Platform | Scribus | Qt binding | Phase 1 (interactive) | Phase 2 (headless) |
|---|---|---|---|---|
| Windows 11 | 1.7.3 | PyQt6 6.10.2 | **125/125 PASS** | **8/8 PASS** |
| Debian 13 | 1.6.3 | PySide2 | **132/134 PASS, 2 skip** | **11/11 PASS** |

The Linux skips are gated features that need Scribus 1.7+ — see [Scribus version requirements per feature](#scribus-version-requirements-per-feature). Re-run anytime with `pytest tests/` and `SCRIBUS_MCP_LIVE=1`. See:

- [doc/BEST_PRACTICES.md](doc/BEST_PRACTICES.md) — house style for driving the MCP (also exposed as the `best_practices` prompt so an LLM session can pull it directly).
- [doc/COOKBOOK.md](doc/COOKBOOK.md) — end-to-end recipes for one-pagers, manuals, dashboards, comparison reports, code walkthroughs, PDF forms.
- [doc/SUPPORT.md](doc/SUPPORT.md) — per-Scripter-function support matrix (~140 functions tabulated).
- [doc/threading-and-scribus.md](doc/threading-and-scribus.md) — architectural rationale behind the bridge.

## What's in the box

- **~125 MCP tools** spanning:
  - **Primitives**: document lifecycle, pages, text/image/shape frames, text content + flow + formatting, paragraph & character styles, colors, layers, search/replace.
  - **Object styling**: fill / stroke / shade / transparency / line caps & joins / corner radius / 2-stop gradients.
  - **Typography**: `list_fonts`, `list_fonts_detailed`, `list_monospace_fonts`, `font_is_available`, plus pre-launch *custom font staging* via `install_custom_font` (copies to a managed dir + patches Scribus's prefs `ExtraFontDirs`).
  - **Export**: `export_pdf`, `render_page_to_image` (inlines a base64 PNG straight into the model's context), `preflight_check`.
  - **PDF interactivity** ([forms package](src/scribus_mcp/tools/forms/)): 6 form fields (text, checkbox, radio, combo, list, push button), 4 annotation types (link, URI, file, sticky-note), JS action setter/getter for all 10 field events.
  - **High-level patterns** (one call → composed multi-element output): `create_radar_chart`, `create_bar_chart`, `create_pie_chart`, `create_timeline`, `create_callout_box`, `create_kpi_tile`, `create_comparison_table`, `create_qr_code_block`, `create_dot_label`, `create_numbered_badge`, **`create_code_sample` (Pygments-tokenized syntax-highlighted code blocks)**.
  - **Region-shaped layouts**: `create_two_column_text`, `create_text_with_image`, `create_section_header`, `create_hero_band`, `create_numbered_steps`, `create_image_caption`, `create_table_of_contents`, `create_sidebar_layout`, `create_kpi_row`, `create_equal_columns`, `create_card_grid`.
  - **Markdown bridge**: `import_markdown` turns a Markdown document into a stack of styled Scribus frames in one call.
- 4 **MCP resources** exposing read-only document state (`scribus://document/info`, `…/colors`, `…/fonts`, `…/missing-resources`).
- 3 **MCP prompts**: `best_practices` (rules + patterns an LLM should follow when driving the MCP — pull this at session start), `manual_from_markdown`, `data_merge_csv`.
- A gated `run_script` escape hatch for arbitrary Scripter Python (off by default).
- Both stdio and Streamable HTTP transports.
- A **Python helper** for caller-side scripts: `from scribus_mcp.layout import PageCursor`. Tracks the running y for a column so multi-band scripts (the demos in `scripts/`, custom batch generators) declare a sequence of bands instead of hand-coding y. See [src/scribus_mcp/layout.py](src/scribus_mcp/layout.py) for the API.

## Requirements

- **Python 3.11+** for the MCP server.
- **Scribus 1.7.x** for the full tool surface. **Scribus 1.6.x** is supported with a small handful of features gated off — see [Scribus version requirements per feature](#scribus-version-requirements-per-feature) below. On Linux Scribus links against system Python — see the distro caveat below.
- For the **interactive** backend: a running Scribus window with the bridge `.spy` file loaded.
- For **headless on Linux servers without a display**: `xvfb` (virtual framebuffer).

### Scribus version requirements per feature

The MCP works on both Scribus 1.6 and 1.7. A small number of tools wrap Scripter functions that were added in 1.7+, so calling them on a 1.6 host returns a structured error to the MCP client instead of letting Scribus's `AttributeError` leak through:

```json
{
  "ok": false,
  "error": "create_qr_code_block (scribus.createBarcode) requires Scribus 1.7.0+ (this Scribus reports 1.6.3). Install / point SCRIBUS_BIN at a 1.7.x build — see README 'Scribus version requirements per feature'.",
  "required_version": "1.7.0",
  "actual_version": "1.6.3"
}
```

The version probe runs once per backend instance (cached via `scribus.scribus_version_info`), so the floor check costs effectively nothing on subsequent calls. An LLM client driving the MCP can match on `required_version` to surface a clean "upgrade Scribus" suggestion to the user.

| Tool | Scripter call | Min Scribus | Notes |
|---|---|---|---|
| `create_qr_code_block` | `scribus.createBarcode` | **1.7.0** | Also needs Ghostscript on the host. |

Everything else in the tool surface (~140 functions) works on both 1.6 and 1.7. If you hit a Scripter `AttributeError` from a tool not in this table, it's likely a missing gate — please file an issue.

### Linux: Python version caveat

Because Scribus on Linux uses *system* Python, the `.spy` bridge runs on whatever your distro ships. The bridge requires Python 3.11+, which means:

| Distro | System Python | Status |
|---|---|---|
| Debian 12 / Ubuntu 23.04+ / Fedora 37+ / Arch | 3.11+ | OK |
| Ubuntu 22.04 LTS / Debian 11 / RHEL 9 | 3.10 or older | Use the Scribus AppImage (bundles its own Python) |

Headless mode has the same constraint, since it also runs Scribus's Python.

## Install

### Step 1 — install Scribus

| Platform | How |
|---|---|
| **Linux** (Debian 12 / Ubuntu 23.04+ / Fedora 37+) | `sudo apt install scribus xvfb` (or distro equivalent) |
| **Linux** (older — Ubuntu 22.04 LTS, etc., or distros that only ship 1.6) | `scribus-mcp --fetch-appimage` (see [Auto-fetch the Scribus AppImage](#auto-fetch-the-scribus-appimage) below), or download the AppImage manually from [scribus.net](https://www.scribus.net/downloads/) and `chmod +x` it. |
| **Windows** | Installer from [scribus.net](https://www.scribus.net/downloads/) — default path `C:\Program Files\Scribus 1.7.3\` |
| **macOS** | `brew install --cask scribus` or download from [scribus.net](https://www.scribus.net/downloads/) |

#### Auto-fetch the Scribus AppImage

If your distro only ships Scribus 1.6 (Debian 13, Ubuntu 24.04, etc.) — or you'd rather not install Scribus system-wide — the MCP can pull the official 1.7.x AppImage for you. Two entry points:

```bash
# (A) Explicit one-shot install — prints the installed path on stdout
scribus-mcp --fetch-appimage
# → /home/<user>/Applications/Scribus-1.7.3-x86_64.AppImage

# (B) Lazy fetch — set the env var; the MCP fetches on first call when no Scribus is found
SCRIBUS_MCP_AUTO_APPIMAGE=1 scribus-mcp
```

Either way, the AppImage lands at `~/Applications/Scribus-X.Y.Z-x86_64.AppImage`, which `scribus-mcp` already probes by default — no `SCRIBUS_BIN` tweak needed afterwards. Subsequent runs are idempotent (the file isn't redownloaded).

**Caveats** (Linux only; the AppImage doesn't apply to macOS / Windows):

- Pulls ~140 MB from SourceForge over HTTPS. Off by default.
- Upstream doesn't ship a SHA256 file alongside the AppImage. The default path verifies via TLS + a 50 MB sanity floor (truncated downloads / HTML error pages get rejected). To pin a hash you computed yourself, use `--appimage-sha256 <hex>` or `SCRIBUS_MCP_APPIMAGE_SHA256=<hex>`.
- AppImages need **FUSE** to mount — `sudo apt install fuse` on Debian/Ubuntu if Scribus fails to launch with `dlopen()` errors.

Override knobs (CLI flag → env var fallback):

| Flag | Env var | Default |
|---|---|---|
| `--appimage-url` | `SCRIBUS_MCP_APPIMAGE_URL` | SourceForge URL for the pinned default version |
| `--appimage-version` | `SCRIBUS_MCP_APPIMAGE_VERSION` | `1.7.3` |
| `--appimage-sha256` | `SCRIBUS_MCP_APPIMAGE_SHA256` | (no pin — TLS only) |
| `--appimage-install-dir` | `SCRIBUS_MCP_APPIMAGE_INSTALL_DIR` | `~/Applications/` |

### Step 2 — install the MCP server

Recommended path uses [`uv`](https://docs.astral.sh/uv/) (one-line installer in [uv's docs](https://docs.astral.sh/uv/getting-started/installation/)). `uvx` runs Python apps in cached isolated envs — no manual venv, no global install.

```bash
# Once published to PyPI (canonical form):
uvx scribus-mcp --help

# Pre-PyPI (today): run straight from GitHub
uvx --from git+https://github.com/caewa/scribus-mcp scribus-mcp --help
```

That's all you need if the only consumer is the MCP server — Claude spawns it on demand (see [Connect Claude](#connect-claude-to-it)). Auto-launch handles starting Scribus + bridge for you on the first interactive call.

If you want `scribus-mcp` on `PATH` directly (e.g. to run `scribus-mcp --print-bridge-path` from a shell), use `uv tool install scribus-mcp` (or `pipx install scribus-mcp`) once it's on PyPI; pre-PyPI, swap in `git+https://github.com/caewa/scribus-mcp`.

### Dev mode (editable install from source)

For contributors / anyone hacking on the MCP itself: clone the repo and install editable. Edits to `src/scribus_mcp/**` take effect immediately, no reinstall.

```bash
git clone https://github.com/caewa/scribus-mcp
cd scribus-mcp

# Option A — uv (recommended)
uv sync                       # creates .venv with all deps
uv pip install -e ".[dev]"    # editable install + dev extras (pytest, ruff)

# Option B — plain pip
python3.11 -m venv .venv
.venv/bin/activate            # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Verify
scribus-mcp --help            # the editable install puts this on PATH
pytest                        # 52 unit tests (no Scribus needed)
SCRIBUS_MCP_LIVE=1 pytest     # full Phase 1/2 suite (needs Scribus + bridge)
```

In dev mode, your MCP client config uses the bare command — your editable install is already on PATH:

```json
{
  "mcpServers": {
    "scribus": {
      "command": "scribus-mcp",
      "env": { "SCRIBUS_BIN": "C:\\Program Files\\Scribus 1.7.3\\scribus.exe" }
    }
  }
}
```

Auto-launch is wired in: any tool call with `mode="interactive"` will spawn Scribus + load the bridge for you if no bridge is already running. No need to manually run the launch command at the start of every session.

### Windows: Scribus path

If Scribus isn't at the default path, point the server at it:

```powershell
$env:SCRIBUS_BIN = "C:\path\to\scribus.exe"
```

(Or set it per-MCP-client in the `env` block — see below.)

## Connect Claude to it

### Claude Code (stdio)

Add to your Claude Code settings (`~/.claude/settings.json` or via `claude mcp add`):

```json
{
  "mcpServers": {
    "scribus": {
      "command": "uvx",
      "args": ["scribus-mcp"],
      "env": {
        "SCRIBUS_BIN": "/usr/bin/scribus"
      }
    }
  }
}
```

`uvx` fetches the package on first use, caches it, then runs the binary. No manual `pip install` step.

> **Pre-PyPI note:** until `scribus-mcp` is published to PyPI, swap the `args` for the git form:
>
> ```json
> "args": ["--from", "git+https://github.com/caewa/scribus-mcp", "scribus-mcp"]
> ```

On Windows replace the env value with `"C:\\Program Files\\Scribus 1.7.3\\scribus.exe"`. If you've done a persistent install (`uv tool install` / `pipx install`), or you're in [dev mode](#dev-mode-editable-install-from-source), use `"command": "scribus-mcp"` directly with no `args`.

### Streamable HTTP (CI, remote, with progress streaming)

```bash
uvx scribus-mcp --http :8765           # zero-install
# or, if installed:
scribus-mcp --http :8765
```

Point your MCP client at `http://localhost:8765/mcp`. Use this transport for long-running headless jobs — it streams progress updates in real time, where stdio would block.

## Enable the interactive backend

The interactive backend lets the MCP drive a Scribus window you already have open — fast IPC, persistent doc state, and you can watch (or take over) the work in real time. The server also works headless-only without it; this is opt-in.

The bridge runs *inside* Scribus and dispatches MCP calls onto Scribus's Qt main thread via a `QTimer`. **It needs a Qt Python binding** (PyQt6 / PyQt5 / PySide6 / PySide2 — whichever Scribus's Python can import) to keep Scribus's GUI responsive while serving requests. Without one, the bridge falls back to a main-thread blocking loop that freezes the GUI — usable only with `-g` (headless) Scribus.

### Step 1 — Install a matching Qt binding

| Platform | Command |
|---|---|
| **Linux** (Debian/Ubuntu) | `sudo apt install python3-pyqt6` (system Python is what Scribus uses) |
| **Linux** (Fedora) | `sudo dnf install python3-pyqt6` |
| **Windows** | Run `scripts/install-pyqt-windows.ps1` **as Administrator**. It auto-detects Scribus's bundled Qt version and installs a matching `PyQt6==<MAJOR>.<MINOR>.*`. (Scribus 1.7.3 ships Qt 6.10.3; PyQt6 6.10.* is the right ABI.) |
| **macOS** | `brew install pyqt6` (system) — but Scribus on macOS uses a bundled Python; details vary. |

> **Why a matching version?** PyQt6's PyPI wheel bundles its own Qt6 DLLs. If those don't match Scribus's bundled Qt6 minor version, `import PyQt6.QtCore` fails with `ImportError: DLL load failed`. The install script reads `Qt6Core.dll`'s FileVersion and pins PyQt6 to the same minor.

### Step 2 — Locate the bridge file

```bash
scribus-mcp --print-bridge-path
```

(Or directly: `src/scribus_mcp/bridge/scribus_mcp_bridge.spy`.)

### Step 3 — Launch Scribus with the bridge

> **Tip:** the MCP **auto-launches** Scribus + bridge whenever a tool call with `mode="interactive"` finds no live bridge. You only need to run this manually if you want Scribus open *before* making the first call (e.g., to position windows or load a doc first).

The simplest path for a test session:

```bash
# Linux
scribus --console -py "$(scribus-mcp --print-bridge-path)"
```

```powershell
# Windows
& "C:\Program Files\Scribus 1.7.3\scribus.exe" --console -py "C:\Users\William\scribus-mcp\src\scribus_mcp\bridge\scribus_mcp_bridge.spy"
```

Dismiss the welcome dialog (if any). Confirm the bridge picked up Qt by inspecting the log:

- **Linux/macOS**: `cat $XDG_RUNTIME_DIR/scribus-mcp/bridge.log`
- **Windows**: `Get-Content "$env:LOCALAPPDATA\scribus-mcp\bridge.log"`

You should see a line like:
```
scribus_mcp_bridge: listening on 127.0.0.1:<port> qt=PyQt6 discovery=...
```

If `qt=` says `NONE-thread-fallback`, the Qt binding isn't being detected — re-check Step 1.

### Step 4 — The bridge writes a discovery file

The MCP server reads `<runtime-dir>/scribus-mcp/scribus-mcp.json` automatically (port + auth token). Once that file exists, every tool call with `mode="auto"` (or `"interactive"`) is routed to your live Scribus instead of spawning a new one.

### Step 5 — Skip the "New Document" startup dialog

By default Scribus shows a New Document wizard at every launch, which **blocks `-py` script execution** until dismissed. Disable it once with:

```powershell
# Windows — close Scribus first, then:
& .\scripts\disable-startup-dialog-windows.ps1
```

```bash
# Linux — close Scribus first, then:
./scripts/disable-startup-dialog-linux.sh
```

Both set `ShowStartupDialog="0"` in your user prefs (`%APPDATA%\Scribus\scribusXYZ.rc` on Windows, `~/.config/scribus/scribusXYZ.rc` on Linux), where `XYZ` is the Scribus minor version (`172`, `163`, …). Persistent across launches; reversible with `-Enable` / `--enable`; use `-Force` / `--force` for non-interactive flows (CI, auto-spawn). You can also flip it manually via `File → Preferences → General → uncheck "Always show 'New Document' dialog at startup"`.

> **First-run note:** the prefs file is created by Scribus on its first save, so you need to launch Scribus once and exit (you can dismiss the welcome dialog inline) before either script can find a file to edit. macOS uses the same XML; the helper for it is TBD.

### Optional: autoload at Scribus startup

If your Scribus build ships ScripterNG (note: not standard in Scribus 1.7.3 Windows), drop the `.spy` in:

- **Linux**: `~/.scribus/scripterng/autoload/`
- **Windows**: `%APPDATA%\Scribus\scripterng\autoload\`
- **macOS**: `~/Library/Preferences/Scribus/scripterng/autoload/`

Otherwise stick with the explicit `-py` launch (Step 3).

## Run the dangerous escape hatch

`run_script` lets the model execute arbitrary Python inside Scribus's interpreter. It's **disabled by default**. To enable it:

```bash
scribus-mcp --enable-run-script        # CLI flag
SCRIBUS_MCP_RUN_SCRIPT=1 scribus-mcp   # or env var
```

For production / shared deployments: keep it off and add purpose-built tools instead. For experimenting locally: fine to enable.

## Configuration

All env vars are optional:

| Variable | Default | What it does |
|---|---|---|
| `SCRIBUS_BIN` | auto-detected | Path to Scribus executable |
| `SCRIBUS_MCP_RUN_SCRIPT` | `0` | Set to `1` to register the `run_script` tool |
| `SCRIBUS_MCP_USE_XVFB` | `0` | Set to `1` to wrap Scribus invocations in `xvfb-run -a` |
| `SCRIBUS_MCP_LOG_LEVEL` | `INFO` | Python log level |
| `SCRIBUS_MCP_EXTRA_FONT_PATHS` | _(empty)_ | `os.pathsep`-separated list of directories to register as Scribus *Additional Font Paths* per headless spawn. Lets a CI worker drop fonts in a known location and have headless jobs see them without modifying the user's persistent Scribus prefs. Each spawn gets a fresh temp prefs dir cleaned up after the call. |
| `SCRIBUS_MCP_AUTO_APPIMAGE` | `0` | Set to `1` to auto-fetch the official Scribus AppImage (Linux only) when no Scribus binary is resolvable. See [Auto-fetch the Scribus AppImage](#auto-fetch-the-scribus-appimage). |
| `SCRIBUS_MCP_APPIMAGE_URL` | _(SourceForge URL for the pinned default version)_ | Override the AppImage download URL. |
| `SCRIBUS_MCP_APPIMAGE_VERSION` | `1.7.3` | Override the version tag used in the installed filename and the default URL. |
| `SCRIBUS_MCP_APPIMAGE_SHA256` | _(empty)_ | Pin a SHA256 to verify the downloaded AppImage against. Upstream doesn't publish one — you compute it yourself. |
| `SCRIBUS_MCP_APPIMAGE_INSTALL_DIR` | `~/Applications/` | Override the AppImage install directory. |

## Tool surface

A non-exhaustive selection (run `scribus-mcp` with [MCP Inspector](https://github.com/modelcontextprotocol/inspector) or check [doc/SUPPORT.md](doc/SUPPORT.md) for the full list):

- **Document**: `create_document`, `open_document`, `save_document`, `save_document_as`, `close_document`, `get_document_info`, `set_document_metadata`
- **Pages**: `add_page`, `delete_page`, `goto_page`, `get_page_count`, `apply_master_page`, `list_master_pages`, `create_master_page`
- **Frames**: `create_text_frame`, `create_image_frame`, `create_rectangle`, `create_ellipse`, `create_line`, `create_polygon`, `create_polyline`, `create_bezier_line`, `create_path_text`, `delete_object`, `move_object`, `resize_object`, `list_page_objects`
- **Text**: `set_text`, `append_text`, `get_text`, `get_visible_text`, `link_text_frames`, `is_text_overflowing`, `set_font`, `set_font_size`, `set_text_color`, `set_text_alignment`, `set_text_vertical_alignment`, `set_line_spacing`
- **Fonts**: `list_fonts`, `list_fonts_detailed`, `list_monospace_fonts`, `get_text_frame_font`, `font_is_available`, `install_custom_font`, `list_extra_font_dirs`
- **Styles**: `list_paragraph_styles`, `apply_paragraph_style`, `apply_character_style`, `import_styles_from_file`
- **Object styling**: `set_fill_color`, `set_line_color`, `set_fill_shade`, `set_line_shade`, `set_fill_transparency`, `set_line_transparency`, `set_line_width`, `set_line_style`, `set_line_cap`, `set_line_join`, `set_corner_radius`, `apply_gradient`, `clear_gradient`, plus matching getters
- **Colors**: `define_color_cmyk`, `define_color_rgb`, `list_colors`, `delete_color`
- **Images**: `load_image`, `set_image_scale`, `scale_image_to_frame`, `set_image_offset`
- **Layers**: `create_layer`, `delete_layer`, `list_layers`, `set_active_layer`, `send_to_layer`, `set_layer_visible`, `set_layer_printable`
- **Search**: `find_and_replace_text`, `find_objects`
- **Export**: `export_pdf`, `render_page_to_image` (returns inline image to Claude), `preflight_check`
- **PDF forms**: `create_pdf_text_field`, `create_pdf_checkbox`, `create_pdf_radio_button`, `create_pdf_combo_box`, `create_pdf_list_box`, `create_pdf_push_button`, `create_link_annotation`, `create_uri_annotation`, `create_file_annotation`, `create_text_annotation`, `set_js_action`, `get_js_action`, `is_annotated`
- **Patterns** (composed multi-element outputs): `create_radar_chart`, `create_bar_chart`, `create_pie_chart`, `create_timeline`, `create_callout_box`, `create_kpi_tile`, `create_comparison_table`, `create_qr_code_block`, `create_dot_label`, `create_numbered_badge`, `create_code_sample`
- **Layouts** (region-shaped): `create_two_column_text`, `create_text_with_image`, `create_section_header`, `create_hero_band`, `create_numbered_steps`, `create_image_caption`, `create_table_of_contents`, `create_sidebar_layout`, `create_kpi_row`, `create_equal_columns`, `create_card_grid`
- **High-level**: `import_markdown` (Markdown → frames)
- **Escape**: `run_script` (gated)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Claude Code  │  Anthropic API  │  Other MCP clients│
└─────────────────────┬───────────────────────────────┘
                      │ stdio  OR  Streamable HTTP
                      ▼
       ┌──────────────────────────────────┐
       │      scribus-mcp (Python 3.11+)  │
       │  Tools / Resources / Prompts     │
       │            │                     │
       │  ┌─────────┴──────────┐          │
       │  │ Headless           │          │
       │  │   ↳ scribus -g -py │          │
       │  │ Interactive        │          │
       │  │   ↳ TCP loopback   │          │
       │  └────────┬───────────┘          │
       └───────────┼──────────────────────┘
                   ▼
       ┌──────────────────────────────────┐
       │  Scribus 1.7.x                   │
       │  (one-shot OR persistent + .spy) │
       └──────────────────────────────────┘
```

## License

MIT

# Scribus Scripter API support matrix

Status of every Scribus 1.7 Scripter function we have considered, broken down by category. The goal is to help you (or an agent) quickly answer:

> "Can scribus-mcp do X?" — and if not, "where is the gap?"

## Legend

| Mark | Meaning |
|---|---|
| **Yes** | Exposed as a dedicated MCP tool (or as a documented arg of one). Full coverage, validation, structured response. |
| **Partial** | Reachable via the `script` body of another tool (e.g. used inside `create_numbered_badge`, `preflight_check`, `markdown_import`) but not a tool of its own. Available to power users who pass raw Python; not a first-class MCP verb. |
| **No** | Not exposed. Either out of scope for now, or low value compared to building blocks already shipped. |
| **N/A** | Function exists in the Scripter API but is non-deterministic in headless mode (modal dialogs, busy cursors, etc.) — covered only inside the bridge for diagnostics. |

The "MCP tool" column points to the verb name a caller should look up. Multiple Scripter functions can map to one tool when the higher-level shape is more useful (e.g. `apply_gradient` wraps `setGradientFill`).

## How to verify on your install

The tables below are curated from the Scribus 1.7 Scripter sources and our own usage. Scribus may add or rename functions between point releases. If you suspect a drift, run this from inside Scribus (Script → Execute Script):

```python
import scribus, json, os
api = sorted(a for a in dir(scribus) if not a.startswith('_') and callable(getattr(scribus, a)))
log = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'scribus-mcp', 'api.txt')
with open(log, 'w', encoding='utf-8') as f:
    for name in api:
        f.write(name + '\n')
scribus.messageBox('scribus-mcp', f'Wrote {len(api)} names to:\n{log}')
```

The resulting `api.txt` is the ground truth for your Scribus build.

---

## Document lifecycle

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `newDocument` | **Yes** | Create a new document (size, margins, orientation, units, columns). | `create_document` |
| `newDocDialog` | **No** | Pops the New Document modal. | Modal — out of scope for MCP. |
| `closeDoc` | **Yes** | Close current document. | `close_document` |
| `haveDoc` | **Yes** | Returns True if any doc is open. | `has_document` (also surfaced via `scribus://document/info`). |
| `openDoc` | **Yes** | Open an existing `.sla`. | `open_document` |
| `saveDoc` | **Yes** | Save under existing path. | `save_document` |
| `saveDocAs` | **Yes** | Save to a new path. | `save_document_as` |
| `revertDoc` | **Yes** | Reload from disk discarding edits. | `revert_document`. |
| `getDocName` | **Yes** | Path of the current document. | `get_document_name`. |
| `setUnit` / `getUnit` | **Yes** | Document unit (mm, pt, in, p, cm, c). | `get_unit` / `set_unit` (string-based). MCP geometry tools still take mm regardless. |
| `setRedraw` / `redrawAll` | **No** | Toggle / force canvas redraw. | Bridge handles redraws at job boundaries; not exposed. |
| `setInfo` | **Yes** | Set Title / Author / Description metadata. | Via `set_document_metadata`. |
| `getInfo` (if present) | **No** | Read back metadata. | Not in 1.7 surface in our reads — file ground-truth check above. |
| `progressReset` / `progressSet` / `progressTotal` | **No** | UI progress bar. | Out of scope for headless flow. |

## Pages

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `pageCount` | **Yes** | Number of pages. | `get_page_count` |
| `currentPage` | **Yes** | Index of current page. | `get_current_page` |
| `gotoPage` | **Yes** | Jump to a page. | `goto_page` |
| `newPage` | **Yes** | Insert a page (before/after). | `add_page` |
| `deletePage` | **Yes** | Delete a page. | `delete_page` |
| `movePage` | **Yes** | Reorder pages. | `move_page(from_page, to_page, position=before/after/at_end)` |
| `getPageSize` / `pageDimension` | **Yes** | Width/height of current page in mm. | `get_page_size` (forces mm; also surfaced via `scribus://document/info`). |
| `getPageMargins` | **Yes** | Read page margins (top/left/right/bottom in mm). | `get_page_margins`. |
| `setPageMargins` | **Yes** | Write page margins (mm). | `set_page_margins` (reorders args around Scribus's asymmetric C signature). |
| `getHGuides` / `setHGuides` | **Yes** | Horizontal guide y-positions (mm). | `get_horizontal_guides` / `set_horizontal_guides`. |
| `getVGuides` / `setVGuides` | **Yes** | Vertical guide x-positions (mm). | `get_vertical_guides` / `set_vertical_guides`. |
| `masterPageNames` | **Yes** | List all master pages. | `list_master_pages` |
| `createMasterPage` | **Yes** | Create a master page. | `create_master_page` |
| `applyMasterPage` | **Yes** | Apply master to a page. | `apply_master_page` |
| `deleteMasterPage` | **Yes** | Remove a master page. | `delete_master_page`. |
| `editMasterPageMode` / `closeMasterPageMode` | **No** | Switch into master-page editor. | Modal — out of scope. |

## Frames & object creation

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `createText` | **Yes** | Text frame at (x, y, w, h). | `create_text_frame`, also used internally by every text-bearing pattern. |
| `createImage` | **Yes** | Image frame. | `create_image_frame`, `create_image_caption`. |
| `createRect` | **Yes** | Rectangle. | `create_rectangle`, used by all card/callout patterns. |
| `createEllipse` | **Yes** | Ellipse / circle. | `create_ellipse`. |
| `createLine` | **Yes** | Single straight line. | `create_line`. |
| `createPolyLine` | **Yes** | Open polyline. | `create_polyline`. |
| `createPolygon` | **Yes** | Closed polygon. | `create_polygon`. Takes `list[tuple[float, float]]` of points in mm. |
| `createBezierLine` | **Yes** | Bezier curve. | `create_bezier_line`. |
| `createPathText` | **Yes** | Text along a path. | `create_path_text`. |
| `createBarcode` | **Yes** | Barcode/QR code. | `create_qr_code_block` pattern. |
| `createTable` | **No** | Native Scribus table object. | Not yet — `create_comparison_table` builds a grid of rects/text instead. |
| `createCustomLineStyle` | **No** | Define a multi-segment line style. | Out of scope. |
| `groupObjects` | **Yes** | Group a list of objects by name. | `group_objects` (returns the new group's name). |
| `unGroupObjects` | **No** | Ungroup. | Not yet. |
| `combinePolygons` | **No** | Boolean union of polygons. | Not yet. |
| `duplicateObject` / `copyObject` / `pasteObject` | **No** | Clipboard ops. | Not yet. |
| `deleteObject` | **Yes** | Remove an object. | `delete_object`. |
| `objectExists` | **Yes** | Test name presence. | `object_exists`. |
| `selectObject` / `deselectAll` / `selectionCount` / `getSelectedObject` | **No** | Selection model. | Tools take object names directly; no global selection in headless flow. |

## Object geometry & manipulation

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `moveObject` | **Yes** | Move by delta. | `move_object(absolute=False)`. |
| `moveObjectAbs` | **Yes** | Move to absolute coordinates. | `move_object(absolute=True)`. Also used internally by `create_numbered_badge` to recenter outlined glyphs. |
| `sizeObject` | **Yes** | Resize an object. | `resize_object`. |
| `rotateObject` / `rotateObjectAbs` | **Yes** | Rotate by delta / to absolute angle. | `rotate_object(absolute=False/True)`. |
| `scaleGroup` | **Yes** | Scale a group proportionally. | `scale_group(name, factor)`. |
| `getPosition` | **Yes** | (x, y) of object in mm. | `get_object_position` (forces mm before reading). |
| `getSize` | **Yes** | (w, h) of object in mm. | `get_object_size` (forces mm before reading). |
| `traceText` / `outlineText` | **Yes** | Convert text frame to vector outlines. | `outline_text` (returns the names of generated polygons). |
| `lockObject` / `isLocked` | **Yes** | Lock/unlock for editing. | `set_object_locked(name, locked)` (idempotent — reads first, toggles only if needed) and `is_object_locked`. |
| `getName` / `renameObject` | **Yes** | Read/write object name. | `get_object_name` / `rename_object` (returns disambiguated name). |
| `getProperty` / `setProperty` / `getPropertyCType` / `getPropertyType` | **Partial** | Generic Qt property reflection. | Used by the `find_objects` search path. Powerful but rarely needed directly. |
| `itemNumberFromName` | **No** | Resolve name to internal index. | Not relevant — we never expose internal indices. |

## Text content & flow

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `setText` | **Yes** | Replace a frame's text. | `set_text` (and used inside ~25 other tools). |
| `insertText` | **Partial** | Insert at offset. | Used inside `append_text`. |
| `deleteText` | **No** | Delete a range. | Not yet. |
| `getAllText` | **Yes** | Full story text. | `get_text`. |
| `getFrameText` | **Yes** | Only laid-out (visible) text. | `get_visible_text`. May return empty if not yet laid out. |
| `selectText` | **Partial** | Select a character range. | Used internally by `create_image_caption`, `create_code_sample`, `import_markdown`. Combined with `setTextColor` to apply per-range colors. |
| `selectAll` | **No** | Select entire story. | Not yet. |
| `getTextLines` | **No** | Number of laid-out lines. | Not yet. |
| `getTextLength` | **No** | Character count of story. | Not yet. |
| `linkTextFrames` | **Yes** | Link frames into a chain. | `link_text_frames`. |
| `unlinkTextFrames` | **No** | Break a link. | Not yet. |
| `textOverflows` | **Yes** | True if frame has overset text. | `is_text_overflowing`. |
| `layoutText` / `layoutTextChain` | **Yes** | Force re-layout. | `layout_text(chain=False/True)`. |

## Text formatting

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `setFont` | **Yes** | Set font of a frame. | `set_font`. |
| `getFont` | **Yes** | Read font of a frame. | `get_text_frame_font`. |
| `setFontSize` | **Yes** | Set point size. | `set_font_size`. |
| `getFontSize` | **No** | Read point size. | Easy add if asked. |
| `setTextColor` | **Yes** | Set text fill color (per-range with `selectText`). | `set_text_color` + used inside `create_image_caption`, `create_code_sample`, `import_markdown`. |
| `setTextShade` | **Yes** | Tint text color 0–100. | `set_text_shade`. |
| `setTextAlignment` | **Yes** | left / center / right / justify / forced. | `set_text_alignment`. |
| `setTextVerticalAlignment` | **Yes** | top / center / bottom. | `set_text_vertical_alignment`. |
| `setLineSpacing` | **Yes** | Set leading in pt. | `set_line_spacing`. |
| `setLineSpacingMode` | **No** | Fixed / automatic / baseline. | Not yet. |
| `setColumns` / `setColumnGap` | **No** | Multi-column text in a single frame. | Not yet — multi-column layouts use multiple frames + `link_text_frames`. |
| `setUnderline` / `setStrikethrough` / `setOutline` / `setShadow` | **No** | Type style toggles. | Not yet. |
| `setTextScalingH` / `setTextScalingV` | **No** | Horizontal/vertical scale. | Not yet. |
| `setFirstLineOffset` | **No** | First-line offset mode. | Not yet. |

## Paragraph & character styles

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `getParagraphStyles` | **Yes** | List paragraph style names. | `list_paragraph_styles`. |
| `getCharStyles` | **Yes** | List character style names. | `list_character_styles`. |
| `setParagraphStyle` | **Yes** | Apply paragraph style by name. | `apply_paragraph_style`. |
| `setCharacterStyle` | **Yes** | Apply character style by name. | `apply_character_style`. |
| `loadStylesFromFile` | **Yes** | Import styles from another `.sla`. | `import_styles_from_file`. |
| `defineParagraphStyle` / `defineCharStyle` | **No** | Programmatically define a style. | Not yet — Scribus 1.7 surface here is unstable. Recommended path: design in the GUI, then `loadStylesFromFile`. |

## Color management

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `getColorNames` | **Yes** | All defined color names. | `list_colors`. |
| `getColor` / `getColorAsRGB` / `getColorAsCMYK` | **No** | Read components of a defined color. | Easy add if asked. |
| `defineColorCMYK` | **No** | CMYK 0–255 ints. | Use `define_color_cmyk` (float). |
| `defineColorCMYKFloat` | **Yes** | CMYK 0.0–100.0. | `define_color_cmyk`. |
| `defineColorRGB` | **Yes** | RGB 0–255. | `define_color_rgb` + auto-called by `create_code_sample` for syntax token colors. |
| `defineColorLab` | **No** | Lab color. | Not yet. |
| `deleteColor` | **Yes** | Delete; replaces uses with given color. | `delete_color`. |
| `replaceColor` | **No** | Substitute one color for another in document. | Not yet. |
| `isSpotColor` / `setSpotColor` | **No** | Spot-color flag. | Not yet. |

## Object styling (fill, stroke, gradient)

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `setFillColor` / `getFillColor` | **Yes** | Fill color. | `set_fill_color` / `get_fill_color`. |
| `setLineColor` / `getLineColor` | **Yes** | Stroke color. | `set_line_color` / `get_line_color`. |
| `setFillShade` | **Yes** | Fill tint 0–100 (cast to int). | `set_fill_shade`. |
| `setLineShade` | **Yes** | Stroke tint 0–100. | `set_line_shade`. |
| `getFillShade` / `getLineShade` | **No** | Read tints. | Easy add if asked. |
| `setFillTransparency` / `setLineTransparency` | **Yes** | Opacity 0.0–1.0. | `set_fill_transparency`, `set_line_transparency`. |
| `getFillTransparency` / `getLineTransparency` | **No** | Read opacity. | Easy add. |
| `setFillBlendmode` / `setLineBlendmode` | **No** | Blend mode (Multiply, Screen, ...). | Not yet. |
| `setLineWidth` / `getLineWidth` | **Yes** | Stroke width pt. | `set_line_width` / `get_line_width`. |
| `setLineStyle` | **Yes** | Solid / dash / dot / etc. | `set_line_style`. |
| `setLineCap` | **Yes** | Flat / round / square. | `set_line_cap`. |
| `setLineJoin` | **Yes** | Miter / round / bevel. | `set_line_join`. |
| `setCornerRadius` / `getCornerRadius` | **Yes** | Rounded rect radius (int-cast). | `set_corner_radius` / `get_corner_radius`. |
| `setGradientFill` | **Yes** | 2-stop gradient (none / horizontal / vertical / diagonal / cross / radial). | `apply_gradient`, `clear_gradient`. Radial anchors at the bbox corner by default — see the docstring for the centering caveat. |
| `setGradientStop` | **No** | Multi-stop gradient. | Scribus exposes a 2-stop subset only; design multi-stop gradients in the GUI and import the .sla. |
| `setGradientVector` | **No** | Custom gradient start / end / focal points. | Reachable via `script` body but not yet wrapped — the 1.7 signature takes 8+ args (start, end, focal, scale, skew) and we don't have a typed shape for it yet. |
| `setMultiLine` / `setCustomLineStyle` | **No** | Apply a multi-segment line style. | Not yet. |

## Images

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `loadImage` | **Yes** | Load file into image frame. | `load_image`, `create_image_caption`. |
| `setImageOffset` | **Yes** | Offset image inside frame. | `set_image_offset`. |
| `setImageScale` | **Yes** | Manual scale factors. | `set_image_scale`. |
| `setScaleImageToFrame` | **Yes** | Auto scale + proportional flag. | `scale_image_to_frame`. |
| `setScaleFrameToImage` | **No** | Resize frame to image's pixel size. | Easy add if asked. |
| `getImageScale` | **No** | Read current scale. | Not yet. |
| `getImageFile` | **Yes** | Path of loaded image. | `get_image_file`. |
| `getImageColorSpace` | **No** | RGB / CMYK / grayscale. | Not yet. |
| `imageGetColors` / `imageGetCMYK` | **No** | Pixel inspection. | Not yet — outside MCP scope. |

## Layers

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `getLayers` | **Yes** | List layer names. | `list_layers`. |
| `getActiveLayer` | **No** | Read active. | Not yet. |
| `setActiveLayer` | **Yes** | Switch active. | `set_active_layer`. |
| `createLayer` | **Yes** | Create. | `create_layer`. |
| `deleteLayer` | **Yes** | Delete. | `delete_layer`. |
| `sendToLayer` | **Yes** | Move object to layer. | `send_to_layer`. |
| `setLayerVisible` | **Yes** | Show/hide. | `set_layer_visible`. |
| `setLayerPrintable` | **Yes** | Toggle printable flag. | `set_layer_printable`. |
| `setLayerLock` / `getLayerLock` | **No** | Lock/unlock layer. | Not yet. |
| `setLayerOutlined` / `setLayerFlow` / `setLayerBlendmode` / `setLayerTransparency` | **No** | Layer rendering flags. | Not yet. |
| `isLayerVisible` / `isLayerPrintable` / etc. | **No** | Read flags. | Not yet. |

## Search & inspection

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `getPageItems` | **Yes** | List `(name, type, info)` per page. | `list_page_objects` (also used internally by `find_objects`, `preflight_check`, all resources). |
| `getAllObjects` | **No** | Cross-page version. | Use `find_objects` (which iterates pages). |
| `isAnnotated` | **Yes** | True if object is a PDF annotation; returns metadata tuple. | `is_annotated`. |
| `isPDFBookmark` | **No** | True if object is a bookmark. | Not yet. |

## Export

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `PDFfile` (class) | **Yes** | PDF export configuration object. | Used by `export_pdf` (preset, range, compression, fonts embed/subset). |
| `ImageExport` (class) | **Yes** | Page-to-image export. | Used by `render_page_to_image` (PNG, base64-inlined as MCP image content). |
| `saveAsImage` (instance method) | **Partial** | Image export call. | Inside `render_page_to_image`. |
| Preflight | **Yes (custom)** | We re-implement preflight in Python by walking `getPageItems` + `getFontNames`. | `preflight_check` (returns issues + used fonts). |
| `placeEPS` / `placeSVG` / `placeVector` / `placeODT` | **No** | Place external vector/document. | Not yet. |

## PDF annotations & forms

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `createPdfAnnotation` | **Yes** | Create a PDF form field (button, text, checkbox, radio, combo, list, sticky note, link, 3D). | All 6 form-field tools (`create_pdf_text_field`, `create_pdf_checkbox`, `create_pdf_radio_button`, `create_pdf_combo_box`, `create_pdf_list_box`, `create_pdf_push_button`). 3D annotations require OSG and aren't exposed. |
| `setLinkAnnotation` | **Yes** | Internal page link on a text frame. | `create_link_annotation` (auto-creates frame if needed). All numeric args are int-cast. |
| `setURIAnnotation` | **Yes** | External URL link. | `create_uri_annotation`. |
| `setFileAnnotation` | **Yes** | Link to an external file (relative / absolute). | `create_file_annotation`. |
| `setTextAnnotation` | **Yes** | Sticky-note PDF annotation with icon. | `create_text_annotation` (9 icons). |
| `setJSActionScript` | **Yes** | Attach JS to a field event. | `set_js_action`, also used inline by `create_pdf_push_button`. |
| `getJSActionScript` | **Yes** | Read JS on an event. | `get_js_action`. |
| `isPDFBookmark` / `setPDFBookmark` | **No** | PDF bookmarks. | Not yet. |

## UI / dialogs / app state

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `messageBox` | **N/A** | Modal message. | Used by the bridge for fatal-error reporting only. Tools never invoke modals. |
| `valueDialog` / `inputDialog` / `fileDialog` / `newStyleDialog` | **N/A** | Other modals. | Out of scope — modals don't fit MCP request/response. |
| `statusMessage` / `setBookmark` / `haveSpellCheck` | **No** | App utilities. | Not yet — low value for headless. |
| `zoomDocument` / `getZoomFactor` / `scrollDocument` | **No** | Canvas viewport. | Not yet — interactive-only utility. |
| `setBusyCursor` | **No** | Cursor toggle. | Not yet. |
| `runScribusCommand` | **No** | Invoke a Scribus action by name. | Not yet — surface is brittle. |

## Fonts

| Scripter function | Supported | Description | MCP tool / remarks |
|---|---|---|---|
| `getFontNames` | **Yes** | Flat list of font names. | `list_fonts`. |
| `getXFontNames` | **Yes** | Detailed (family, name, file, ps_name, embed). | `list_fonts_detailed`. |
| `getFont` | **Yes** | Frame's current font. | `get_text_frame_font`. |
| `setFont` | **Yes** | Set frame's font. | `set_font` + auto-resolved by `create_code_sample`. |
| (no Scripter equivalent) | **Partial** | Add a new font at runtime. | Not possible via Scripter — Scribus only scans fonts at startup. We expose a *staging* path: `install_custom_font` copies the .ttf/.otf/.ttc/.pfa/.pfb into a managed dir and patches Scribus's per-user prefs XML to add that dir to *Additional Font Paths*. Takes effect on the **next Scribus launch**. |
| `list_extra_font_dirs` (MCP-only) | **Yes** | Read additional font dirs registered in Scribus's prefs. | `list_extra_font_dirs`. |
| `list_monospace_fonts` (MCP-only) | **Yes** | Filter loaded fonts by name heuristic. | `list_monospace_fonts` — used as a fallback by `create_code_sample` when no `font` is passed. |
| `font_is_available` (MCP-only) | **Yes** | Check before applying — `setFont` raises if absent. | `font_is_available`. |

## Tables (Scribus native tables)

The 1.7 native-table API (`createTable`, `setCellText`, `mergeCells`, ...) is **not** exposed. The `create_comparison_table` pattern composes rectangles + text frames instead, which is more flexible across Scribus versions and lets us customize per-cell styling. If you need a real Scribus table object (with linked-cell editing in the UI), open one in the GUI and import via `loadStylesFromFile` / save as template.

---

## Summary

Coverage is biased toward what an LLM actually needs to author a publication: layout, styling, typography, images, color, and PDF export with forms. Items in the **No** column are typically:
- read-back accessors that are easy to add on demand (`getFontSize`, `getActiveLayer`, …)
- modal / interactive-only surfaces that don't fit the MCP request/response shape
- low-traffic features (spot colors, lab color, multi-stop gradients) that we'll add when a real workflow needs them

If you hit a function that's in **No** and would unblock a real task, file it and we'll wire a tool. The `script` tool (raw Python passthrough) is also available as an escape hatch for anything we haven't promoted yet.

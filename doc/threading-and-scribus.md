# Threading and Scribus: why the bridge looks the way it does

This file captures the threading/IPC constraints we hit while building the
interactive bridge, the dead ends we walked into, and the architecture that
actually works. Future contributors: read this before "simplifying" the
bridge — most of the apparent complexity is load-bearing.

## The core constraint

**Scribus's Scripter API must be called from the Qt main thread.**

The `scribus` module exposed inside Scribus is a thin Python binding over
C++ code that touches Qt objects: documents, pages, text frames, images,
the canvas. Qt enforces that "GUI" objects (and many of its non-GUI objects
that participate in signal/slot dispatch) only be touched on the thread that
created the `QApplication` — i.e. the main thread.

Calling Scripter from a worker thread produces undefined behavior. In
practice that's mostly a hard crash (segfault), sometimes silent corruption,
occasionally a Python exception. We verified this empirically on Windows:
calling `scribus.newDocument(...)` from a worker thread crashes Scribus
~100% of the time.

Read-only Scripter calls (`haveDoc`, `getColorNames`, `pageCount`) seem to
sometimes work from a worker thread — but only because they happen to not
touch Qt's machinery. Don't rely on it. Treat *all* Scripter calls as
main-thread-only.

## What an MCP bridge needs

The MCP server is a separate process. It speaks to Scribus over TCP loopback.
For each tool call the bridge has to:

1. Accept a TCP connection (network I/O — should not block the GUI).
2. Parse the JSON request (CPU work).
3. **Invoke the Scripter call (must be on Scribus's main thread).**
4. Serialize the result and write it back.

Steps 1, 2, and 4 are fine on a worker thread. Step 3 is the trap.

## The architecture: listener thread + main-thread dispatcher

```
TCP loopback (127.0.0.1)
        │
        ▼
┌────────────────────────────┐
│  listener thread (daemon)  │   accepts connections, parses JSON,
│                            │   validates auth token, enqueues to inbox.
└────────────┬───────────────┘   Pure I/O — never calls Scripter.
             │
             ▼
        ┌───────┐
        │ inbox │   thread-safe Queue
        └───┬───┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│  main thread: drains inbox + invokes Scripter + replies     │
│                                                             │
│  TWO POSSIBLE IMPLEMENTATIONS:                              │
│                                                             │
│  (A) QTimer-based — when PyQt6 is importable                │
│      A QTimer fires every 20ms on Qt's main-thread event    │
│      loop. The slot drains the inbox synchronously. Qt      │
│      keeps processing GUI events between firings → UI       │
│      stays responsive.                                      │
│                                                             │
│  (B) Blocking dispatch loop — when no Qt binding exists     │
│      The .spy script never returns; instead its main loop   │
│      blocks on `inbox.get(timeout=...)` and dispatches.     │
│      Qt's event loop is starved → in GUI mode this freezes  │
│      the window. Only viable in `-g` (headless) mode.       │
└─────────────────────────────────────────────────────────────┘
```

Both implementations live in `src/scribus_mcp/bridge/scribus_mcp_bridge.spy`.
The bridge probes for a Qt binding (`PyQt6.QtCore` first, then PyQt5,
PySide6, PySide2) and picks A if it finds one, B otherwise.

## Dead ends we walked through (so you don't have to)

### 1. `while True` on the main thread without yielding
First version. Loop sleeps 10 ms between queue polls and calls
`scribus.processEvents()` defensively. **Result: GUI shows "Application not
responding" within seconds.** `processEvents()` either doesn't exist on this
Scribus build or doesn't process enough events under tight Python loops.
Even if it worked, the Python GIL makes the loop hostile to Qt's needs.

### 2. Worker thread dispatches Scripter calls
Second version. Listener thread accepts and queues; a *second* worker thread
calls `_handle()` (which invokes Scripter). Plausible because daemon threads
sound "free", but **`scribus.newDocument(...)` crashed Scribus immediately**
the first time we triggered it — exactly the main-thread rule biting us.
Read-only calls happened to work, which made the bug feel like a flake
until we tried a mutating call.

### 3. Pure stdlib QTimer alternative (e.g. signal-based wakeup)
Considered. There's no portable way for a worker thread to "ask the main
thread to please run this callback now" without something like Qt's
`postEvent`. CPython's `signal` module is too coarse and signal handlers
have their own thread-affinity rules. **Skipped.**

### 4. Win32 timer via ctypes (SetTimer / WM_TIMER)
Considered. `SetTimer` would push WM_TIMER messages into Scribus's window
message pump, which Qt processes; we'd register a callback. Possible but
fragile — bypasses Qt's signal/slot machinery, would need a window handle,
and would only work on Windows. **Skipped in favor of pursuing PyQt6.**

### 5. Persistent worker thread on the *main* thread (oxymoron)
We considered moving the dispatch loop *into* the main thread itself,
without Qt — i.e. the .spy doesn't return, its main loop is the dispatcher.
This is implementation B above and it works for `-g` (headless) only
because there's no GUI event loop to starve.

## The ABI conflict that nearly sank PyQt6 on Windows

Even after deciding "use PyQt6 if available", Windows hit a second wall:

- Scribus 1.7.3 ships its own bundled Qt 6.10.3 DLLs in its install dir.
- PyQt6 (latest at time of writing: 6.11.0) bundles **its own** Qt 6.11.0 DLLs.
- When Scribus loads first, the process has Qt6Core 6.10.3 mapped in. When
  Python then imports `PyQt6.QtCore`, Windows's loader returns the
  already-mapped Qt6Core — but `QtCore.pyd` was compiled against 6.11.0
  symbols, some of which don't exist in 6.10.3. **`ImportError: DLL load
  failed while importing QtCore: The specified procedure could not be found`**.

The fix is to install a PyQt6 version whose bundled Qt matches Scribus's
Qt minor version. For Scribus 1.7.3 that's `pip install "PyQt6==6.10.*"`.
The `scripts/install-pyqt-windows.ps1` helper auto-detects Scribus's Qt
version (by reading `Qt6Core.dll`'s FileVersion) and installs the matching
PyQt6.

## Lifetime: keeping the script "alive"

A separate problem from threading: when Scribus runs a `.spy` via
`Script → Execute Script…` or `-py`, the script context is torn down once
the script returns. Daemon threads spawned by the script die with it.

For the QTimer path (A), the timer is registered on Qt's event loop *as a
QObject owned by Qt*. Qt holds a reference, so it survives the script
returning. We also stash other live state (socket, listener thread, timer)
on the `scribus` module via `setattr` so Python's GC doesn't reclaim them.
Result: script returns, Qt keeps firing the timer, bridge serves indefinitely.

For the blocking path (B), the script *doesn't* return. The dispatch loop
runs forever (until the user kills Scribus). State persistence is a
non-issue because the script frame is still live.

## Summary table

| Mode | Launch | Qt binding present | Works? | UX |
|---|---|---|---|---|
| Headless (one-shot) | `scribus -g -py job.py` | irrelevant | ✓ | Slow (~3s/call). Stateless. |
| Headless (persistent) | `scribus -g -ns -py bridge.spy` | no | ✓ (path B) | Invisible Scribus + bridge. Fast. |
| Headless (persistent) | `scribus -g -ns -py bridge.spy` | yes | exits — no event loop for QTimer | not useful |
| Interactive (visible GUI) | `scribus -ns -py bridge.spy` | no | bridge serves but GUI freezes (path B) | unshippable |
| **Interactive (visible GUI)** | `scribus -ns -py bridge.spy` | **yes (PyQt6 matching ABI)** | ✓ (path A) | **GUI responsive, bridge live, full feature set.** |

The last row is the one we want for v1. It requires the user to install a
matching PyQt6 once via `scripts/install-pyqt-windows.ps1` (or its Linux
equivalent — usually `apt install python3-pyqt6` Just Works there because
Scribus on Linux links against system Python and system Qt).

## Files involved

- [src/scribus_mcp/bridge/scribus_mcp_bridge.spy](../src/scribus_mcp/bridge/scribus_mcp_bridge.spy) — the bridge itself (paths A and B coexist)
- [src/scribus_mcp/backends/interactive.py](../src/scribus_mcp/backends/interactive.py) — server-side TCP client
- [scripts/install-pyqt-windows.ps1](../scripts/install-pyqt-windows.ps1) — Qt-version-aware PyQt6 installer
- [tests/test_phase1_interactive.py](../tests/test_phase1_interactive.py) — live integration tests covering these paths

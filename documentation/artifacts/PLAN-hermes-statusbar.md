# PLAN: Hermes-style StatusBar + TUI Layout Polish

## Status
- **Created**: 2026-05-13
- **Status**: completed
- **Branch**: main

## Context

The science-cli TUI is modular (6 files in `tui/`) but missing the Hermes-style status bar and has minor spacing issues in the input area. The goal is to add a `StatusBar` widget that shows theme/context/timer and refine the compose order/layout to match the exact Hermes layout.

---

## Phase 1: Create `tui/status_bar.py`

### New File: `status_bar.py`

Create a `StatusBar` widget class with:

**Imports:**
- `from textual.app import ComposeResult`
- `from textual.widgets import Static`
- `from textual.timer import Timer`
- `from science_cli.core.session import load_session`
- `from science_cli import __version__`

**Class: `StatusBar(Static)`**

**Class-level CSS:**
```python
DEFAULT_CSS = """
StatusBar {
    height: 1;
    width: 100%;
    padding: 0 1;
    color: #888888;
}
"""
```

**Internal state:**
- `_start_time: float` — set in `on_mount()` using `time.time()`
- `_timer: Timer | None` — managed timer reference

**Reactive attributes:**
- `theme_name: reactive[str]` — current theme name
- `project: reactive[str]` — last_project from session
- `protocol: reactive[str]` — last_protocol from session
- `step: reactive[str]` — last_step from session

**`__init__`:** Accept `app: SCIApp` reference so it can call `app.refresh_status_bar()`

**`compose()` → `ComposeResult`:**
```python
yield Static("", id="statusbar-content")
```

**`on_mount()`:**
1. Load session: `sess = load_session()`
2. Set `self.project = sess.get("last_project", "")`, etc.
3. Set `self.theme_name = sess.get("theme", "publication-acs")`
4. Record `_start_time = time.time()`
5. Call `self._update_display()`
6. Set interval: `self._timer = self.set_interval(1, self._tick)`

**`_tick()` method:**
1. Call `self._update_display()` to refresh the display

**`_update_display()` method — build the status string:**

Format: `theme(ctx) │ ctx project/protocol/step │ 45s`

Steps:
1. Get `theme_name` from `load_session().get("theme", "publication-acs")` (updated each tick to reflect live changes)
2. If `project`: amber-colored project, else show `--` in dim grey
3. If `protocol`: cyan-colored protocol
4. If `step`: dim step
5. Format: `theme │ ctx project/protocol/step │ elapsed`

Using RichText for colors:
```python
parts = []
parts.append(("[#888888]", f"{self.theme_name}"))
parts.append("[#888888] │ ctx ")

if self.project:
    parts.append(f"[#d4a853]{self.project}[/]")   # amber
else:
    parts.append("[#666666]--[/]")

if self.protocol:
    parts.append(f"[#5ea8b5]/{self.protocol}[/]")  # cyan

if self.step:
    parts.append(f"[#888888]/{self.step}[/]")

# elapsed time
import time
elapsed = int(time.time() - self._start_time)
if elapsed < 60:
    timer_str = f"{elapsed}s"
elif elapsed < 3600:
    timer_str = f"{elapsed // 60}m"
else:
    timer_str = f"{elapsed // 3600}h"
parts.append(f" [#888888]│ {timer_str}")
```

**`refresh_from_session()` — called by app after command execution:**
```python
def refresh_from_session(self) -> None:
    sess = load_session()
    self.project = sess.get("last_project", "")
    self.protocol = sess.get("last_protocol", "")
    self.step = sess.get("last_step", "")
    self.theme_name = sess.get("theme", "publication-acs")
    self._update_display()
```

**`watch_*` methods** — after any reactive attribute changes, call `self._update_display()`.

---

## Phase 2: Modify `tui/__init__.py`

Add `StatusBar` to imports:
```python
from science_cli.tui.status_bar import StatusBar
__all__ = ["SCIApp", "StatusBar"]
```

---

## Phase 3: Modify `tui/app.py`

### 3a. Add import
```python
from science_cli.tui.status_bar import StatusBar
```

### 3b. Modify `compose()` — insert StatusBar between OutputPanel and `sep-input-top`

Current:
```python
yield Container(
    SCIBanner(),
    TuiHeader(),
    OutputPanel(),
    Static(id="sep-input-top"),
    Horizontal(
        Static("\u276f ", id="input-prompt"),
        CommandInput(),
    ),
    Static(id="sep-input-bottom"),
)
```

New:
```python
yield Container(
    SCIBanner(),
    TuiHeader(),
    OutputPanel(),
    StatusBar(self),   # ← INSERT HERE
    Static(id="sep-input-top"),
    Horizontal(
        Static("\u276f ", id="input-prompt"),
        CommandInput(),
    ),
    Static(id="sep-input-bottom"),
)
```

### 3c. Add `refresh_status_bar()` method to `SCIApp`

```python
def refresh_status_bar(self) -> None:
    """Called after a command changes session context to refresh the status bar."""
    try:
        status_bar = self.query_one(StatusBar)
        status_bar.refresh_from_session()
    except Exception:
        pass
```

### 3d. Modify `on_mount()` — add timer interval

Add after the welcome message block:
```python
# Start status bar timer (StatusBar manages its own interval internally via set_interval)
# The status bar is already running via set_interval in its on_mount
# Just refresh once to pick up initial session state
self.refresh_status_bar()
```

Also remove the redundant welcome message in `on_mount()` since `OutputPanel.on_mount()` already shows one — but check: `OutputPanel.on_mount()` IS called when the widget is mounted, so we should NOT duplicate in `SCIApp.on_mount()`. However, `SCIApp.on_mount()` currently writes a SECOND welcome message. Fix this by removing the welcome message from `SCIApp.on_mount()` (since `OutputPanel.on_mount()` handles it).

### 3e. Add call to `refresh_status_bar()` after command execution

In `on_input_submitted()`, after handling fzf commands and non-fzf commands, when session state changes:

After:
```python
if new_project != header.context_project or new_protocol != header.context_protocol:
    header.set_context(project=new_project, protocol=new_protocol)
```

Add:
```python
self.refresh_status_bar()
```

### 3f. CSS — fix separator spacing

Add to the `CSS` string:
```python
StatusBar {
    color: #888888;
}
#sep-input-top, #sep-input-bottom {
    color: #55AA55;
    height: 1;
    padding: 0;
    margin: 0;
}
```

Ensure the `Container` has no extra padding:
```python
Container {
    padding: 0;
    margin: 0;
}
```

---

## Phase 4: Modify `tui/output_panel.py`

### Update `on_mount()` welcome message

Current:
```python
self.write("")
self.write(
    "[bold #55ee77]SCI TUI[/] — Scientific Data Analysis CLI\n"
    "[dim]Type commands below. [/dim]"
    "[dim #5ea8b5]/help[/] [dim]for slash commands, [/dim]"
    "[dim #5ea8b5]/clear[/] [dim]to clear output.[/dim]\n"
)
```

New:
```python
self.write("")
self.write(f"[bold #55ee77]myscience v{__version__}[/]")
self.write(f"[dim]Type commands below. [/dim]"
           f"[dim #5ea8b5]/help[/] [dim]/clear[/] [dim]/history[/] [dim]/version[/dim]")
self.write(f"[dim]✦ Tip: use [bold]--fzf[/] for interactive file selection[/dim]\n")
```

Also remove the `self.write("")` at the top since the first write is already a newline.

---

## Phase 5: Verify file structure

After all changes:
```
tui/
  __init__.py        → exports SCIApp, StatusBar
  app.py             → imports StatusBar, composes it, timer interval, refresh calls
  banner.py          → UNCHANGED
  theme.py           → UNCHANGED
  header.py          → UNCHANGED
  output_panel.py    → updated welcome message
  input_bar.py       → UNCHANGED
  status_bar.py      → NEW
```

---

## Test Plan

1. **Syntax check:**
   ```bash
   python -c "from science_cli.tui.app import SCIApp; print('OK')"
   ```
2. **Compile check:**
   ```bash
   python -m py_compile src/science_cli/tui/status_bar.py
   python -m py_compile src/science_cli/tui/app.py
   python -m py_compile src/science_cli/tui/output_panel.py
   ```
3. **Import check:**
   ```bash
   python -c "from science_cli.tui import SCIApp, StatusBar; print('OK')"
   ```
4. **Manual test:**
   ```bash
   sci
   ```
   - Check banner renders correctly (ASCII art in green)
   - Check header: `(sci project/protocol) v7.0.0 | 1.project 2.protocol...`
   - Check output panel shows welcome + tip about --fzf
   - **NEW**: Check status bar shows `theme │ ctx project/protocol/step │ 45s`
   - Timer should tick up every second
   - After running a command (e.g., `open -m project myproj`), status bar should update

---

## Implementation Order

1. `tui/status_bar.py` — CREATE (new file, no dependencies)
2. `tui/__init__.py` — MODIFY (add export)
3. `tui/output_panel.py` — MODIFY (welcome message)
4. `tui/app.py` — MODIFY (compose order, timer, CSS, refresh calls)

---

## Files Summary

| File | Action | Change |
|------|--------|--------|
| `tui/status_bar.py` | CREATE | New StatusBar widget with theme, context, timer |
| `tui/__init__.py` | MODIFY | Export StatusBar |
| `tui/app.py` | MODIFY | Add StatusBar to compose, timer interval, `refresh_status_bar()` calls, CSS fixes |
| `tui/output_panel.py` | MODIFY | Updated welcome message with `myscience` branding and `--fzf` tip |

## What NOT to Change

- `banner.py` — ASCII art is correct
- `theme.py` — colors are correct
- `header.py` — two-column layout is correct
- `input_bar.py` — no border, height 1 is correct
- Any command dispatch, fzf capture, session save/restore logic
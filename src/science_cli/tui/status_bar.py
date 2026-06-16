"""Hermes-style StatusBar widget — shows theme, context, and elapsed timer.

Displays a compact status line below the output panel with:
- Current theme name
- Active context (project/protocol/step)
- Elapsed session timer

Updates every second and on command execution to reflect live session state.
"""

import time

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static

from science_cli.core.session import load_session


class StatusBar(Static):
    """A compact status bar showing theme, context, and session timer.

    Extends Textual's Static to provide a self-updating status line
    that reflects the current session state. The display format is:

        theme │ ctx project/protocol/step │ 45s

    Uses reactive attributes for project, protocol, step, and theme_name
    so the display auto-updates when any context changes.

    The timer ticks every second to update the elapsed time display.
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        width: 100%;
        padding: 0 1;
        color: #888888;
    }
    """

    theme_name: reactive[str] = reactive("publication-nature")
    project: reactive[str] = reactive("")
    protocol: reactive[str] = reactive("")
    step: reactive[str] = reactive("")

    def __init__(self, app=None) -> None:
        """Initialize the StatusBar with an optional app reference.

        Args:
            app: The SCIApp instance, used for refresh_status_bar() callback.
        """
        super().__init__()
        self._app_ref = app
        self._start_time: float = 0.0
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Yield the inner content widget."""
        yield Static("", id="statusbar-content")

    def on_mount(self) -> None:
        """Load session state, record start time, and start the timer."""
        sess = load_session()
        self.project = sess.get("last_project", "")
        self.protocol = sess.get("last_protocol", "")
        self.step = sess.get("last_step", "")
        self.theme_name = sess.get("theme", "publication-nature")

        self._start_time = time.time()
        self._update_display()

        # Tick every second to update the elapsed timer.
        self._timer = self.set_interval(1, self._tick)

    def _tick(self) -> None:
        """Called every second by the timer to refresh the display."""
        self._update_display()

    def _update_display(self) -> None:
        """Build the status string and update the inner Static widget.

        Format: theme │ ctx project/protocol/step │ elapsed
        """
        # Re-read session each tick to pick up live theme changes.
        sess = load_session()
        theme = sess.get("theme", "publication-nature")

        parts: list[str] = []

        # Theme name
        parts.append(f"[#888888]{theme}[/]")

        # Separator
        parts.append("[#888888] │[/] ctx ")

        # Project (amber) or placeholder (dim grey)
        if self.project:
            parts.append(f"[#d4a853]{self.project}[/]")
        else:
            parts.append("[#666666]--[/]")

        # Protocol (cyan)
        if self.protocol:
            parts.append(f"[#5ea8b5]/{self.protocol}[/]")

        # Step (dim)
        if self.step:
            parts.append(f"[#888888]/{self.step}[/]")

        # Elapsed timer
        elapsed = int(time.time() - self._start_time)
        if elapsed < 60:
            timer_str = f"{elapsed}s"
        elif elapsed < 3600:
            timer_str = f"{elapsed // 60}m"
        else:
            timer_str = f"{elapsed // 3600}h"
        parts.append(f" [#888888]│[/] {timer_str}")

        status = "".join(parts)
        try:
            inner = self.query_one("#statusbar-content", Static)
            inner.update(status)
        except Exception:
            pass

    def refresh_from_session(self) -> None:
        """Refresh all context from the session file and update display.

        Called by SCIApp after command execution to pick up any
        changes to last_project, last_protocol, last_step, or theme.
        """
        sess = load_session()
        self.project = sess.get("last_project", "")
        self.protocol = sess.get("last_protocol", "")
        self.step = sess.get("last_step", "")
        self.theme_name = sess.get("theme", "publication-nature")
        self._update_display()

    def watch_theme_name(self, value: str) -> None:
        """React to theme_name changes."""
        self._update_display()

    def watch_project(self, value: str) -> None:
        """React to project changes."""
        self._update_display()

    def watch_protocol(self, value: str) -> None:
        """React to protocol changes."""
        self._update_display()

    def watch_step(self, value: str) -> None:
        """React to step changes."""
        self._update_display()

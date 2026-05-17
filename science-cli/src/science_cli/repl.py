"""SCI REPL — prompt_toolkit Application with TUI-style layout.

Uses the alternate screen to present a persistent header (ASCII SCI banner,
version, session info) above a scrollable output area and a fixed input bar
at the bottom — matching the TUI's look and feel.
"""

import io
import sys
import shlex
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

from rich.console import Console as RichConsole

from science_cli import __version__
from science_cli.cli.commands import COMMAND_TREE
from science_cli.core.session import load_session, add_history, get_history
from science_cli.tui.banner import SCI_ART

ACCENT = "#55ee77"
DIM = "#888888"
TEXT = "#cccccc"
PROJECT_COL = "#d4a853"
PROTOCOL_COL = "#5ea8b5"
BG = "#0d0d0d"
TERM_WIDTH = 80


def _capture_handler_output(cmd_name: str, cmd_args: list[str]) -> str:
    """Run a COMMAND_TREE handler and capture all output to a string."""
    info = COMMAND_TREE.get(cmd_name)
    if not info:
        return f"Unknown command: {cmd_name}"
    handler = info["handler"]
    buf = io.StringIO()
    capture = RichConsole(file=buf, force_terminal=True, width=120, color_system="truecolor")
    mod = sys.modules.get(handler.__module__)
    saved = None
    if mod and hasattr(mod, "console"):
        saved = mod.console
        mod.console = capture
    try:
        handler(cmd_args)
    except SystemExit:
        pass
    except Exception as e:
        capture.print(f"[#d47a7a]{e}[/]")
    finally:
        if saved is not None:
            mod.console = saved
    return buf.getvalue()


def _build_header() -> FormattedText:
    """Build the persistent header with banner, version, session info."""
    sess = load_session()
    ft = FormattedText()

    # ASCII banner
    for line in SCI_ART.split("\n"):
        ft.append((f"bold {ACCENT}", f"  {line}"))
    ft.append(("", ""))
    ft.append((f"bold {ACCENT}", f"  science-cli v{__version__}"))

    # top separator
    ft.append((DIM, "\n  " + "─" * (TERM_WIDTH - 4)))

    # session info line
    theme = sess.get("theme", "default")
    ft.append((DIM, f"\n  theme: "))
    ft.append((TEXT, theme))
    ft.append((DIM, " │ ctx "))

    proj = sess.get("last_project", "")
    prot = sess.get("last_protocol", "")
    step = sess.get("last_step", "")
    if proj:
        ft.append((PROJECT_COL, proj))
    else:
        ft.append((DIM, "--"))
    if prot:
        ft.append((PROTOCOL_COL, f"/{prot}"))
    if step:
        ft.append((DIM, f"/{step}"))

    # bottom separator
    ft.append((DIM, "\n  " + "─" * (TERM_WIDTH - 4)))
    ft.append(("", "\n"))
    return ft


class SCIRepl:
    """prompt_toolkit Application REPL with TUI-style header/output/input layout."""

    def __init__(self):
        hist_file = Path.home() / ".config" / "science-cli" / "repl_history"
        hist_file.parent.mkdir(parents=True, exist_ok=True)

        self._output_lines: list[str] = []
        self._output_control = FormattedTextControl(self._get_output_text)

        self._input_buffer = Buffer(
            history=FileHistory(str(hist_file)),
            auto_suggest=AutoSuggestFromHistory(),
            accept_handler=self._handle_line,
        )

        self._app = self._build_app()

    # ── output management ──────────────────────────────

    def _get_output_text(self) -> str:
        return "\n".join(self._output_lines)

    def _add_output(self, text: str, style: str = "") -> None:
        if style:
            self._output_lines.append(f"\x1b[0m{text}")
        else:
            self._output_lines.append(text)

    # ── command dispatch ───────────────────────────────

    def _capture_help(self, args: list[str]) -> str:
        """Capture help command output to a string."""
        buf = io.StringIO()
        c = RichConsole(file=buf, force_terminal=True, color_system="truecolor")
        from science_cli.cli.help import show_command_help, show_top_help
        mod = sys.modules.get("science_cli.cli.help")
        saved = getattr(mod, "console", None) if mod else None
        if saved is not None:
            mod.console = c
        try:
            if args:
                show_command_help(args[0])
            else:
                show_top_help()
        finally:
            if saved is not None:
                mod.console = saved
        return buf.getvalue()

    def _handle_line(self, buf: Buffer) -> bool:
        raw = buf.text
        line = raw.strip()
        if not line:
            return True

        add_history(line)
        self._add_output(f">>> {line}")

        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()

        cmd = parts[0]
        args = parts[1:]

        if cmd in ("exit", "quit"):
            self._app.exit()
            return True

        if cmd in ("clear", "cls"):
            self._output_lines.clear()
            self._app.invalidate()
            return True

        if cmd == "help":
            out = self._capture_help(args)
            if out:
                for lo in out.split("\n"):
                    self._add_output(lo)
            self._app.invalidate()
            return True

        if cmd == "history":
            history = get_history()
            if not history:
                self._add_output("(no history)")
            else:
                start = max(0, len(history) - 30)
                for i, h in enumerate(history[start:], start + 1):
                    self._add_output(f"  {i:3d}. {h}")
            self._app.invalidate()
            return True

        if cmd == "version":
            self._add_output(f"sci version {__version__}")
            self._app.invalidate()
            return True

        if cmd in COMMAND_TREE:
            out = _capture_handler_output(cmd, args)
            if out:
                for lo in out.split("\n"):
                    self._add_output(lo)
            self._app.invalidate()
            return True

        self._add_output(f"Unknown: {cmd}")
        self._app.invalidate()
        return True

    # ── layout ─────────────────────────────────────────

    def _build_app(self) -> Application:
        header_window = Window(
            content=FormattedTextControl(_build_header),
            height=13,
            dont_extend_height=True,
            style=f"bg:{BG}",
        )

        output_window = Window(
            content=self._output_control,
            wrap_lines=True,
            scrollable=True,
        )

        input_window = Window(
            content=BufferControl(buffer=self._input_buffer, focusable=True),
            height=1,
            dont_extend_height=True,
        )

        root = HSplit([header_window, output_window, input_window])
        layout = Layout(root)

        kb = KeyBindings()

        @kb.add("c-c")
        @kb.add("c-d")
        def _quit(event) -> None:
            event.app.exit()

        @kb.add("c-l")
        def _clear(event) -> None:
            self._output_lines.clear()
            self._output_control.text = ""
            self._app.invalidate()

        return Application(
            layout=layout,
            key_bindings=kb,
            full_screen=True,
            mouse_support=True,
            style=Style([
                ("sci-prompt", f"bold {ACCENT}"),
                ("output", ""),
            ]),
        )

    # ── entry point ────────────────────────────────────

    def run(self) -> None:
        self._app.layout.focus(self._input_buffer)
        self._app.run()

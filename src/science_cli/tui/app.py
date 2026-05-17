"""Main Textual TUI application — composable SCI interface.

Composes the SCI banner, two-column header, scrollable output panel,
and command input bar into a unified Textual application. Dispatches
commands to the same COMMAND_TREE handlers as the CLI, capturing all
output for display in the output panel.

Bare `sci` (no args) launches this TUI. `sci --repl` still uses the
legacy prompt_toolkit REPL.
"""

import inspect
import io
import re
import shlex
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout

from rich.console import Console as RichConsole
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Static

from science_cli import __version__
from science_cli.cli.commands import COMMAND_TREE
from science_cli.core.session import (
    add_history,
    get_history,
)
from science_cli.tui.banner import SCIBanner
from science_cli.tui.input_bar import CommandInput
from science_cli.tui.output_panel import OutputPanel
from science_cli.tui.status_bar import StatusBar
from science_cli.tui.theme import CSS_VARIABLES

#: Maximum number of command history entries to store.
MAX_HISTORY = 200


def _is_fzf_command(cmd_args: list[str]) -> bool:
    """Check if the command args include an interactive fzf flag."""
    return "--fzf" in cmd_args or "-fzf" in cmd_args


def _capture_handler_output(cmd_name: str, cmd_args: list[str]) -> str:
    """Execute a COMMAND_TREE handler and capture all its output to a string.

    Handlers typically use module-level ``console = Console()`` instances
    and/or ``rprint()`` from Rich. This function:
    1. Creates a Rich Console writing to a StringIO buffer.
    2. Monkey-patches the handler's module ``console`` variable to use the
       capture console (so ``console.print()`` calls are captured).
    3. Redirects ``sys.stdout`` and ``sys.stderr`` to the same buffer
       (so ``rprint()`` and direct ``print()`` calls are captured).
    4. Runs the handler, catching SystemExit and general exceptions.
    5. Restores all patched state.

    Args:
        cmd_name: The command name as registered in COMMAND_TREE.
        cmd_args: The argument list to pass to the handler.

    Returns:
        The captured output as a string. May include ANSI/Rich markup.
        Returns an error message string if the command is unknown.
    """
    info = COMMAND_TREE.get(cmd_name)
    if not info:
        return f"Unknown command: {cmd_name}"

    handler = info["handler"]

    # Create a Rich Console that writes into our capture buffer.
    buf = io.StringIO()
    capture_console = RichConsole(file=buf, force_terminal=True, width=120, color_system="truecolor")

    # Find the handler's module so we can patch its console variable.
    module = inspect.getmodule(handler)
    orig_console = getattr(module, "console", None)

    # Patch the module-level console to capture console.print() calls.
    if orig_console is not None:
        setattr(module, "console", capture_console)

    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            handler(cmd_args)
    except SystemExit:
        # Handlers may call sys.exit(), catch it silently.
        pass
    except Exception as e:
        # Rich markup for styled error display.
        buf.write(f"\n[bold red]Error:[/bold red] {e}\n")
    finally:
        # Restore the original console.
        if orig_console is not None:
            setattr(module, "console", orig_console)

    return buf.getvalue()


def _parse_input_line(line: str) -> tuple[str, list[str]]:
    """Parse an input line into a command name and argument list.

    Uses shell-like tokenization (shlex.split) for proper quote handling.
    Falls back to basic whitespace splitting on parse errors.

    Args:
        line: The raw input string from the user.

    Returns:
        A tuple of (command_name, argument_list).
    """
    line = line.strip()
    if not line:
        return "", []

    try:
        parts = shlex.split(line)
    except ValueError:
        parts = line.split()

    if not parts:
        return "", []

    return parts[0], parts[1:]


class SCIApp(App):
    """The main SCI Textual application.

    Layout (top to bottom):
        ┌─────────────────────────────────────────┐
        │  SCI Banner (ASCII art + version)       │
        ├─────────────────────────────────────────┤
        │  Header (context | workflow)            │
        ├─────────────────────────────────────────┤
        │  Output Panel (scrollable results)      │
        │  ...                                    │
        │  ...                                    │
        ├─────────────────────────────────────────┤
        │  Command Input (prompt + text entry)    │
        └─────────────────────────────────────────┘

    The app listens for command submissions from the input bar,
    dispatches them to COMMAND_TREE handlers, captures output,
    and displays it in the output panel.
    """

    CSS: str = (
        CSS_VARIABLES
        + """
    Screen {
        background: $background;
    }
    SCIApp {
        background: $background;
    }
    StatusBar {
        height: 1;
        color: #888888;
    }
    #sep-input-top, #sep-input-bottom {
        height: 1;
        color: #2a4a2a;
    }
    #input-prompt {
        color: #55ee77;
        width: 2;
        content-align: right middle;
        height: 1;
    }
    CommandInput {
        height: 1;
    }
    #input-row {
        height: 1;
    }
    #sep-input-top, #sep-input-bottom {
        height: 1;
        color: #55AA55;
    }
    #input-prompt {
        color: #55ee77;
        width: 2;
        content-align: right middle;
    }
    # Input row only — SCIBanner has its own height: auto
    CommandInput {
        height: 1;
    }
    #input-prompt {
        height: 1;
    }
    """
    )

    # Sub-widgets declared for type-safe access via query_one().
    # These are Textual's way of declaring composable child widgets
    # with auto-query support.
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+d", "quit", "Quit"),
        ("ctrl+l", "clear_screen", "Clear"),
    ]

    def compose(self) -> ComposeResult:
        """Build the TUI layout — banner, output, input."""
        yield SCIBanner()
        yield OutputPanel()
        yield StatusBar(self)
        yield Static(id="sep-input-top")
        yield Horizontal(
            Static("\u276f ", id="input-prompt"),
            CommandInput(),
            id="input-row",
        )
        yield Static(id="sep-input-bottom")

    def on_mount(self) -> None:
        """Post-mount initialization — focus the input bar and load context."""
        input_bar = self.query_one(CommandInput)
        input_bar.focus()

        self._update_separators()

        self.refresh_status_bar()

    def on_unmount(self) -> None:
        """Clean up TUI-specific state on exit."""

    def refresh_status_bar(self) -> None:
        """Called after a command changes session context to refresh the status bar."""
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.refresh_from_session()
        except Exception:
            pass

    def _update_separators(self) -> None:
        """Set separator lines to full terminal width."""
        w = self.size.width
        if w < 1:
            return
        line = "\u2500" * w
        try:
            self.query_one("#sep-input-top", Static).update(line)
            self.query_one("#sep-input-bottom", Static).update(line)
        except Exception:
            pass

    def on_resize(self, event) -> None:
        """Redraw separators when terminal resizes."""
        self._update_separators()

    def _update_separators(self) -> None:
        """Set separator lines to full terminal width."""
        w = self.size.width
        if w < 1:
            return
        line = "\u2500" * w
        try:
            self.query_one("#sep-input-top", Static).update(line)
            self.query_one("#sep-input-bottom", Static).update(line)
        except Exception:
            pass

    def on_resize(self, event) -> None:
        """Redraw separators when terminal resizes."""
        self._update_separators()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission from the input bar.

        Routes the command based on its type:
        - Empty line: ignored.
        - Slash command (starts with /): handled internally.
        - Known COMMAND_TREE command: dispatched to handler, output captured.
        - Unknown command: error message displayed.

        Args:
            event: The Textual Input.Submitted event containing the input value.
        """
        line = event.value.strip()
        if not line:
            return

        # Record in session history.
        add_history(line)

        # Parse into command + args.
        cmd_name, cmd_args = _parse_input_line(line)

        # Get references to UI components.
        output = self.query_one(OutputPanel)
        input_bar = self.query_one(CommandInput)
        input_bar.clear()

        # --- Slash commands (handled internally) ---
        if cmd_name.startswith("/"):
            self._handle_slash_command(cmd_name, output)
            return

        # --- Built-in commands (handled by the TUI, not COMMAND_TREE) ---
        if cmd_name in ("help", "version", "history", "clear", "cls"):
            self._handle_builtin(cmd_name, cmd_args, output)
            return

        if cmd_name in ("exit", "quit"):
            self.exit()
            return

        # --- COMMAND_TREE dispatch ---
        if cmd_name in COMMAND_TREE:
            # Interactive fzf commands: run the handler in a separate
            # Python process with the real terminal.  This avoids ALL
            # asyncio nesting issues (questionary calls asyncio.run()),
            # terminal-state corruption, and TTY-wrangling problems.
            if _is_fzf_command(cmd_args):
                self._driver.stop_application_mode()
                try:
                    subprocess.run(
                        [sys.executable, "-m", "science_cli", cmd_name] + cmd_args,
                    )
                except KeyboardInterrupt:
                    pass
                except Exception as exc:
                    output.write_error(f"Error running '{cmd_name}': {exc}")
                    return
                finally:
                    self.refresh()
                    self._driver.start_application_mode()

                output.write_command_header(line)
                self.refresh_status_bar()
                return

            # Normal (non-fzf) command: capture output to string.
            captured = _capture_handler_output(cmd_name, cmd_args)
            output.write_command_output(line, captured)

            self.refresh_status_bar()

            # Scroll to bottom after new output.
            output.scroll_end(animate=False)
        else:
            output.write_command_header(cmd_name)
            output.write_error(f"Unknown command: {cmd_name}")
            output.write("[dim]Type /help to see available commands.[/dim]")

    def _handle_slash_command(self, cmd_name: str, output: OutputPanel) -> None:
        """Handle slash commands internally.

        Args:
            cmd_name: The slash command name (e.g., "/help", "/clear").
            output: The OutputPanel to write results to.
        """
        if cmd_name == "/help":
            self._slash_help(output)
        elif cmd_name == "/clear":
            output.clear_output()
        elif cmd_name == "/history":
            self._slash_history(output)
        elif cmd_name == "/version":
            output.write_command_header("/version")
            output.write(f"[bold #55ee77]sci[/] version [bold]{__version__}[/]")
        else:
            output.write_command_header(cmd_name)
            output.write_error(f"Unknown slash command: {cmd_name}")
            output.write("[dim]Available: /help, /clear, /history, /version[/dim]")

    def _handle_builtin(
        self, cmd_name: str, cmd_args: list[str], output: OutputPanel
    ) -> None:
        """Handle built-in commands that the TUI overrides.

        Args:
            cmd_name: The command name (help, version, history, clear).
            cmd_args: Additional arguments for the command.
            output: The OutputPanel to write results to.
        """
        if cmd_name == "help":
            self._slash_help(output)
        elif cmd_name == "version":
            output.write_command_header("version")
            output.write(f"[bold #55ee77]sci[/] version [bold]{__version__}[/]")
        elif cmd_name == "history":
            self._slash_history(output)
        elif cmd_name in ("clear", "cls"):
            output.clear_output()

    def _slash_help(self, output: OutputPanel) -> None:
        output.write_command_header("/help")

        groups: dict[str, list[tuple[str, str]]] = {}
        ungrouped: list[tuple[str, str]] = []

        for cmd_name, info in sorted(COMMAND_TREE.items()):
            desc = info.get("desc", "")
            m = re.search(r"\([Gg]roup\s+(\d+)\)", desc)
            if m:
                g = m.group(1)
                groups.setdefault(g, []).append((cmd_name, desc))
            else:
                ungrouped.append((cmd_name, desc))

        for g in sorted(groups.keys()):
            output.write(f"[bold #55ee77]Group {g}[/]")
            output.write("[dim]Command   │  Description[/dim]")
            output.write("[dim #4A7A4A]──────────┼──────────────────────────────────────────────[/]")
            for cmd_name, desc in groups[g]:
                clean_desc = re.sub(r"\s*\([Gg]roup\s+\d+\)", "", desc)
                output.write(f"[bold]{cmd_name:<10}[/bold]│ {clean_desc}")
            output.write("")

        if ungrouped:
            output.write("[bold #55ee77]Other[/]")
            output.write("[dim]Command   │  Description[/dim]")
            output.write("[dim #4A7A4A]──────────┼──────────────────────────────────────────────[/]")
            for cmd_name, desc in ungrouped:
                output.write(f"[bold]{cmd_name:<10}[/bold]│ {desc}")
            output.write("")

        output.write("[dim]Type a command name followed by --help for command-specific help.[/dim]")

    def _slash_history(self, output: OutputPanel) -> None:
        """Display the recent command history.

        Shows the last 30 commands from the session history file.
        Each entry is numbered and timestamped (session-level timestamp,
        not per-command timestamps).

        Args:
            output: The OutputPanel to write history to.
        """
        output.write_command_header("/history")
        hist = get_history()
        if not hist:
            output.write("[dim]No commands in history.[/dim]")
            return

        start = max(0, len(hist) - 30)
        for i, h in enumerate(hist[start:], start + 1):
            output.write(f"  [dim]{i:3d}.[/dim] {h}")

    def action_quit(self) -> None:
        """Handle Ctrl+C / Ctrl+D — quit the application gracefully."""
        self.exit()

    def action_clear_screen(self) -> None:
        """Handle Ctrl+L — clear the output panel."""
        output = self.query_one(OutputPanel)
        output.clear_output()

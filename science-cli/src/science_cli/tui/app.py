"""Main Textual TUI application — composable SCI interface.

Composes the SCI banner, two-column header, scrollable output panel,
and command input bar into a unified Textual application. Dispatches
commands to the same COMMAND_TREE handlers as the CLI, capturing all
output for display in the output panel.

Bare `sci` (no args) launches this TUI. `sci --repl` still uses the
legacy prompt_toolkit REPL.
"""

import io
import sys
import inspect
import shlex
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime

from rich.console import Console as RichConsole

from textual.app import App, ComposeResult
from textual.containers import Vertical, Container
from textual.widgets import Static, Input

from science_cli import __version__
from science_cli.cli.commands import COMMAND_TREE
from science_cli.core.session import (
    load_session,
    save_session,
    add_history,
    get_history,
)
from science_cli.tui.theme import CSS_VARIABLES, MATCHA_COLORS, RICH_STYLES
from science_cli.tui.banner import SCIBanner
from science_cli.tui.header import TuiHeader
from science_cli.tui.output_panel import OutputPanel
from science_cli.tui.input_bar import CommandInput, SLASH_COMMANDS


#: Maximum number of command history entries to store.
MAX_HISTORY = 200


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
        """Build the TUI layout — banner, header, output, input."""
        yield Container(
            SCIBanner(),
            TuiHeader(),
            OutputPanel(),
            CommandInput(),
        )

    def on_mount(self) -> None:
        """Post-mount initialization — focus the input bar and load context."""
        # Give the input bar focus so the user can type immediately.
        input_bar = self.query_one(CommandInput)
        input_bar.focus()

        # Show a welcome message in the output panel.
        output = self.query_one(OutputPanel)
        output.write(
            f"\n[bold #8BAA89]SCI TUI v{__version__}[/]\n"
            f"[dim]Type commands below. [/dim]"
            f"[dim #6aaa9a]/help[/] [dim]for slash commands, [/dim]"
            f"[dim #6aaa9a]/clear[/] [dim]to clear output.[/dim]\n"
            f"[dim]Ctrl+C or Ctrl+D to quit.[/dim]\n"
        )

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
        header = self.query_one(TuiHeader)
        input_bar = self.query_one(CommandInput)

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
            captured = _capture_handler_output(cmd_name, cmd_args)
            output.write_command_output(line, captured)

            # After command execution, refresh session state
            # (commands like 'open' or 'project open' change context).
            sess = load_session()
            new_project = sess.get("last_project", "")
            new_protocol = sess.get("last_protocol", "")

            if new_project != header.context_project or new_protocol != header.context_protocol:
                header.set_context(project=new_project, protocol=new_protocol)
                input_bar.update_context(project=new_project, protocol=new_protocol)

            # Scroll to bottom after new output.
            output.scroll_end(animate=False)
        else:
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
            output.write(f"[bold #8BAA89]sci[/] version [bold]{__version__}[/]")
        else:
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
            output.add_separator("version")
            output.write(f"[bold #8BAA89]sci[/] version [bold]{__version__}[/]")
        elif cmd_name == "history":
            self._slash_history(output)
        elif cmd_name in ("clear", "cls"):
            output.clear_output()

    def _slash_help(self, output: OutputPanel) -> None:
        """Display the help screen showing available commands and slash commands.

        Lists all registered COMMAND_TREE commands with their descriptions,
        plus the slash commands available in the TUI.

        Args:
            output: The OutputPanel to write help text to.
        """
        output.add_separator("/help")

        output.write("[bold #8BAA89]SCI Commands[/]\n")
        output.write("[dim]Command  │  Description[/dim]")
        output.write("[dim #4A7A4A]──────────┼──────────────────────────────────────────────[/]")

        for cmd_name, info in sorted(COMMAND_TREE.items()):
            desc = info.get("desc", "")
            output.write(f"[bold]{cmd_name:<10}[/bold]│ {desc}")

        output.write("")
        output.write("[bold #8BAA89]Slash Commands[/]\n")
        output.write("[dim]Command     │  Description[/dim]")
        output.write("[dim #4A7A4A]─────────────┼──────────────────────────────────────────────[/]")

        for slash_cmd, desc in sorted(SLASH_COMMANDS.items()):
            output.write(f"[bold]{slash_cmd:<13}[/bold]│ {desc}")

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
        output.add_separator("/history")
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

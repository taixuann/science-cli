"""Scrollable output panel — displays command output with timestamped separators.

Uses Textual's RichLog widget to present formatted command output with
auto-scrolling, timestamp separators, and Rich markup support.
"""

from datetime import datetime

from textual.widgets import RichLog


class OutputPanel(RichLog):
    """A scrollable output display for command results.

    Extends Textual's RichLog to provide:
    - Timestamped command separators before each command output block
    - Auto-scrolling to the bottom when new output arrives
    - Rich markup rendering (colors, bold, tables, panels)
    - Write method for programmatic output (used by capture system)

    The output panel stores a reference to the current screen for
    proper rendering of Rich objects.

    Usage:
        output = OutputPanel()
        output.write_command_output("ls", "Protocol A\n  step-1\n  step-2\\n")
    """

    DEFAULT_CSS: str = """
    OutputPanel {
        height: 1fr;
        width: 100%;
        border: solid $border;
        background: $background;
        color: $text;
        padding: 0 1;
        overflow-y: scroll;
    }
    OutputPanel:focus {
        border: solid $accent;
    }
    """

    def on_mount(self) -> None:
        """Display a welcome message when the output panel first mounts."""
        self.write("")
        self.write(
            "[bold $accent]SCI TUI[/bold $accent] — Scientific Data Analysis CLI\n"
            "[dim]Type commands below. [/dim]"
            "[dim $info]/help[/dim $info] [dim]for slash commands, [/dim]"
            "[dim $info]/clear[/dim $info] [dim]to clear output.[/dim]\n"
        )

    def add_separator(self, command: str = "") -> None:
        """Add a timestamped separator line before command output.

        The separator format is: ``--- HH:MM:SS [command] ---``
        This visually separates each command's output in the scrollable log.

        Args:
            command: The command string to display in the separator.
                     If empty, only the timestamp is shown.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        if command:
            separator = f"[dim $border]--- {ts} [bold $dim]{command}[/bold $dim] ---[/dim $border]"
        else:
            separator = f"[dim $border]--- {ts} ---[/dim $border]"
        self.write(separator)

    def write_command_output(self, command: str, output: str) -> None:
        """Write a complete command result to the panel.

        Adds a timestamped separator followed by the command output.
        If the output is empty, writes a dim "(no output)" message.
        Auto-scrolls to the bottom after writing.

        Args:
            command: The command that was executed (e.g., "ls -m protocol").
            output: The captured output string from the command handler.
        """
        self.add_separator(command)

        if output and output.strip():
            # Split output into lines and write each one.
            # RichLog handles Rich markup in the output text.
            for line in output.rstrip("\n").split("\n"):
                if line.strip():
                    self.write(line)
                else:
                    self.write("")
        else:
            self.write("[dim](no output)[/dim]")

        self.write("")

    def write_error(self, message: str) -> None:
        """Write an error message to the panel.

        Args:
            message: The error message to display (supports Rich markup).
        """
        self.write(f"[bold $error]{message}[/bold $error]")

    def clear_output(self) -> None:
        """Clear all output from the panel and show a fresh welcome message."""
        self.clear()
        self.on_mount()

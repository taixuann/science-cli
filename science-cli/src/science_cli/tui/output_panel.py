"""Scrollable output panel — displays command output with timestamped separators.

Uses Textual's RichLog widget to present formatted command output with
auto-scrolling, timestamp separators, and Rich markup support.
"""

from datetime import datetime

from textual.widgets import RichLog

from rich.table import Table
from rich.text import Text as RichText

from science_cli import __version__


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

    def __init__(self, *, markup: bool = True, **kwargs):
        super().__init__(markup=markup, **kwargs)

    DEFAULT_CSS: str = """
    OutputPanel {
        height: 1fr;
        width: 100%;
        background: transparent;
        color: #cccccc;
        padding: 0 1;
        overflow-y: scroll;
        scrollbar-size-vertical: 0;
        scrollbar-size-horizontal: 0;
        scrollbar-color: #55AA55;
        scrollbar-background: transparent;
    }
    """

    def on_mount(self) -> None:
        """Display a welcome message when the output panel first mounts."""
        self.write(f"[bold #55ee77]myscience v{__version__}[/]")
        self.write(
            f"[dim]Type commands below. [/dim]"
            f"[dim #5ea8b5]/help[/] [dim]/clear[/] [dim]/history[/] [dim]/version[/dim]"
        )
        self.write(f"[dim]Tip: use [bold]--fzf[/] for interactive file selection[/dim]\n")

    def write_command_header(self, command: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        table = Table.grid(padding=0)
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True, justify="right", ratio=1)
        table.add_row(
            RichText(f"> {command}", style="bold #55ee77"),
            RichText(f"  {ts}", style="dim #55AA55"),
        )
        self.write(table)

    def write_command_output(self, command: str, output: str) -> None:
        self.write_command_header(command)
        if output and output.strip():
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
        self.write(f"[bold #d47a7a]{message}[/]")

    def clear_output(self) -> None:
        """Clear all output from the panel and show a fresh welcome message."""
        self.clear()
        self.on_mount()

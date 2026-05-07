"""General built-in command handlers — help, version, clear, history."""

from rich.console import Console
from rich import print as rprint
from science_cli.cli.help import show_top_help, show_command_help

console = Console()


def general_handler(args: list, cmd: str = "") -> None:
    """Handle built-in commands by name."""
    if cmd == "help":
        if args:
            show_command_help(args[0])
        else:
            show_top_help()
    elif cmd == "version":
        from science_cli import __version__
        console.print(f"science-cli version {__version__}")
    elif cmd == "clear":
        console.clear()
    elif cmd == "history":
        from science_cli.core.session import get_history
        history = get_history()
        if not history:
            console.print("[dim]No commands in history.[/dim]")
            return
        start = max(0, len(history) - 30)
        for i, cmd_h in enumerate(history[start:], start + 1):
            console.print(f"  [dim]{i:3d}.[/dim] {cmd_h}")

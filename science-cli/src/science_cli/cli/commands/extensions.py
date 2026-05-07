"""extensions command — list available extension tools."""

from rich.console import Console
from rich import print as rprint

console = Console()


def extensions_handler(args: list) -> None:
    """List all available extensions and their commands."""
    from science_cli.cli.commands import COMMAND_TREE, ALL_COMMANDS

    known_core = {
        "add", "delete", "edit", "ls", "open", "project",
        "plot", "analyze", "config", "techniques", "results",
        "help", "version", "clear", "history", "extensions",
    }

    extensions = {
        name: info
        for name, info in COMMAND_TREE.items()
        if name not in known_core
    }

    if not extensions:
        print("No extension commands registered.")
        return

    rprint("\n[bold]Registered extensions[/bold]\n")
    for name, info in sorted(extensions.items()):
        desc = info.get("desc", "")
        rprint(f"  [cyan]{name:<18}[/cyan] [dim]{desc}[/dim]")
    rprint("")
    rprint("[dim]Use `sci <extension> --help` for details.[/dim]")
    rprint("")

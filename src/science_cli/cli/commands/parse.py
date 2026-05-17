"""parse command handler."""

from pathlib import Path
from rich.console import Console
console = Console()


def _parse_filename(name: str) -> dict:
    """Extract filename components."""
    return {"filename": name, "base": Path(name).stem, "ext": Path(name).suffix}


def _filename_parser_wizard() -> dict:
    """Placeholder wizard."""
    return {}


def parse_handler(args: list) -> None:
    """Handle `parse` command."""
    if args:
        result = _parse_filename(args[0])
        if result:
            console.print("[bold green]Parsed fields:[/bold green]")
            for key, val in result.items():
                console.print(f"  {key}: [bold]{val}[/bold]")
        else:
            console.print("[yellow]No matching pattern. Launching wizard...[/yellow]")
            _filename_parser_wizard()
    else:
        _filename_parser_wizard()

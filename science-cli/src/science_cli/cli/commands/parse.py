"""parse command handler."""

from rich.console import Console
console = Console()


def parse_handler(args: list) -> None:
    """Handle `parse` command."""
    from science_cli.core.legacy import parse_filename, filename_parser_wizard
    if args:
        result = parse_filename(args[0])
        if result:
            console.print("[bold green]Parsed fields:[/bold green]")
            for key, val in result.items():
                console.print(f"  {key}: [bold]{val}[/bold]")
        else:
            console.print("[yellow]No matching pattern. Launching wizard...[/yellow]")
            filename_parser_wizard()
    else:
        filename_parser_wizard()

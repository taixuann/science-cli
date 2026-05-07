"""image command handler — stub."""

from rich.console import Console
console = Console()


def image_handler(args: list) -> None:
    """Handle `image` command."""
    if not args or args[0] in ("--help", "-h"):
        console.print("[yellow]Usage: image analyze <file> (not yet implemented)[/yellow]")
        return
    if args[0] == "analyze" and len(args) > 1:
        from science_cli.commands.image import analyze_image
        analyze_image(args[1])
    else:
        console.print("[yellow]Usage: image analyze <file>[/yellow]")

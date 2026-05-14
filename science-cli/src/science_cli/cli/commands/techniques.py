"""techniques command — list available techniques (deprecated, delegates to config)."""

from rich.console import Console
from rich import print as rprint

console = Console()


def techniques_handler(args: list) -> None:
    """Show available techniques and how to use them (deprecated).

    Delegates to config module's _cmd_list_techniques.
    """
    # Deprecation notice
    rprint("[yellow]⚠ DEPRECATED: Use 'config list techniques' instead.[/yellow]")
    rprint()

    # Delegate to config module's technique listing
    from science_cli.cli.commands.config import _cmd_list_techniques
    _cmd_list_techniques()

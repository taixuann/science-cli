"""init command handler — standalone config initializer."""

from rich.console import Console

from science_cli.cli.commands.config import _cmd_init
from science_cli.cli.help import show_command_help

console = Console()


def init_handler(args: list) -> None:
    """Handle `init` command — delegates to config init logic."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("init")
        return
    _cmd_init(args)

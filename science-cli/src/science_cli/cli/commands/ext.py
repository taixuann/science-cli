"""ext command handler — unified extension dispatch interface.

Usage:
    ext memristor <subcommand> [args...]   — dispatch to memristor extension
    ext list                               — list all available extensions
    ext help <name>                        — show extension help
"""

from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help

console = Console()


# Registry of known extension dispatchers.
# Each entry maps an extension name to a callable that handles subcommands.
# In future phases this will use the ExtensionRegistry from extensions.py.
_EXTENSION_DISPATCHERS: dict[str, callable] = {}


def _register_dispatchers() -> None:
    """Register known extension dispatchers (lazy import to avoid startup cost)."""
    if _EXTENSION_DISPATCHERS:
        return

    # Try importing the memristor extension
    try:
        from science_cli.memristor.device_cli import build_parser

        def _memristor_dispatch(args: list) -> None:
            parser = build_parser()
            parsed = parser.parse_args(args)
            parsed.func(parsed)

        _EXTENSION_DISPATCHERS["memristor"] = _memristor_dispatch
    except ImportError:
        pass  # Memristor extension not installed — skip

    # Future extensions will be registered here or via ExtensionRegistry


def _list_extensions() -> None:
    """List all available extensions from the registry."""
    _register_dispatchers()

    if not _EXTENSION_DISPATCHERS:
        rprint("[yellow]No extensions installed.[/yellow]")
        return

    rprint("\n[bold]Available extensions[/bold]\n")
    for name in sorted(_EXTENSION_DISPATCHERS.keys()):
        # Get help description if available
        if name == "memristor":
            desc = "Crossbar device management (init, add, ls, info, sync, validate, stats, rm, check)"
        else:
            desc = ""
        rprint(f"  [cyan]{name:<18}[/cyan] [dim]{desc}[/dim]")
    rprint("")
    rprint("[dim]Use 'ext help <name>' for subcommand details.[/dim]")
    rprint("[dim]Use 'ext <name> --help' for full command help.[/dim]")
    rprint("")


def _ext_help(name: str) -> None:
    """Show help for a specific extension."""
    if name == "memristor":
        show_command_help("memristor")
    else:
        console.print(f"[yellow]Unknown extension: '{name}'[/yellow]")
        _list_extensions()


def ext_handler(args: list) -> None:
    """Handle `ext` command — unified extension dispatch.

    Subcommands:
        ext memristor <subcommand> [args...]  — dispatch to memristor extension
        ext list                              — list all available extensions
        ext help <name>                       — show extension help
        ext --help                            — show this help
    """
    if not args or args[0] in ("--help", "-h"):
        rprint("\n[bold]ext[/bold] — Unified extension interface\n")
        rprint("  [bold]Usage:[/bold]")
        rprint("    ext <name> <subcommand> [args...]  — dispatch to extension")
        rprint("    ext list                           — list available extensions")
        rprint("    ext help <name>                    — show extension help")
        rprint("\n  [dim]Use 'ext <name> --help' for subcommand details.[/dim]")
        rprint("  [dim]The 'memristor' command is also available standalone (deprecated).[/dim]")
        rprint("")
        return

    _register_dispatchers()

    sub = args[0]
    sub_args = args[1:]

    if sub == "list":
        _list_extensions()
        return

    if sub == "help":
        if not sub_args:
            rprint("[yellow]Usage: ext help <name>[/yellow]")
            _list_extensions()
        else:
            _ext_help(sub_args[0])
        return

    # Subcommand is an extension name — dispatch to it
    dispatcher = _EXTENSION_DISPATCHERS.get(sub)
    if dispatcher is None:
        console.print(f"[yellow]Unknown extension: '{sub}'[/yellow]")
        rprint("[dim]Use 'ext list' to see available extensions.[/dim]")
        return

    try:
        dispatcher(sub_args)
    except SystemExit:
        pass  # argparse calls sys.exit — swallow it

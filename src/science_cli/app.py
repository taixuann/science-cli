"""Entry point — TUI, REPL shell + direct CLI dispatch.

Bare `sci` (no arguments) launches the Textual TUI.
`sci --tui` also launches the TUI.
`sci --repl` launches the prompt_toolkit REPL (TUI-style layout).
All other invocations dispatch to COMMAND_TREE handlers.
"""

import sys

from rich.console import Console

from science_cli import __version__
from science_cli.core.session import add_history, get_history
from science_cli.cli.commands import COMMAND_TREE
from science_cli.cli.help import show_top_help

console = Console()


def run_cli():
    args = sys.argv[1:]

    # Bare `sci` (no args) or `sci --tui` launches the Textual TUI.
    if not args or args[0] in ("--tui",):
        _run_tui()
        return

    if args[0] in ("--help", "-h"):
        show_top_help()
        return

    if args[0] in ("--version", "-V"):
        console.print(f"sci version {__version__}")
        return

    if args[0] in ("--repl",):
        _run_repl()
        return

    cmd = args[0]
    cmd_args = args[1:]

    if cmd in COMMAND_TREE:
        add_history(" ".join(args))
        COMMAND_TREE[cmd]["handler"](cmd_args)
    elif cmd == "help":
        if cmd_args:
            from science_cli.cli.help import show_command_help
            show_command_help(cmd_args[0])
        else:
            show_top_help()
    elif cmd == "version":
        console.print(f"sci version {__version__}")
    elif cmd in ("clear", "cls"):
        console.clear()
    elif cmd == "history":
        hist = get_history()
        if not hist:
            console.print("[dim]No commands in history.[/dim]")
        else:
            start = max(0, len(hist) - 30)
            for i, h in enumerate(hist[start:], start + 1):
                console.print(f"  [dim]{i:3d}.[/dim] {h}")
    else:
        console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
        console.print(f"[dim]Use 'sci --help' to see available commands.[/dim]")
        sys.exit(1)


def _run_tui():
    """Launch the Textual TUI application."""
    from science_cli.tui.app import SCIApp
    app = SCIApp()
    app.run()


def _run_repl():
    from science_cli.repl import run_repl
    run_repl()




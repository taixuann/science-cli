"""REPL shell + direct CLI dispatch — the application entry point."""

import sys
import shutil
from pathlib import Path

from rich.console import Console
from rich import print as rprint
from rich.panel import Panel

from science_cli import __version__
from science_cli.core.session import load_session, add_history, get_history
from science_cli.core.project import get_current_project_path
from science_cli.theme import apply_theme
from science_cli.cli.help import show_top_help
from science_cli.cli.commands import COMMAND_TREE, GENERAL_COMMANDS

console = Console()


def run_cli():
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
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


def _run_repl():
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style

    hist_file = Path.home() / ".config" / "science-cli" / "repl_history"
    hist_file.parent.mkdir(parents=True, exist_ok=True)

    session = PromptSession(
        history=FileHistory(str(hist_file)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    theme = load_session().get("theme", "default")
    apply_theme(theme)

    _show_banner()

    while True:
        ctx = _build_context()
        try:
            line = session.prompt(ctx)
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not line.strip():
            continue

        add_history(line.strip())
        parts = _split_line(line.strip())
        cmd = parts[0]
        cmd_args = parts[1:]

        if cmd in ("exit", "quit"):
            break
        elif cmd in ("clear", "cls"):
            console.clear()
        elif cmd == "help":
            if cmd_args:
                from science_cli.cli.help import show_command_help
                show_command_help(cmd_args[0])
            else:
                show_top_help()
        elif cmd == "history":
            history = get_history()
            if not history:
                console.print("[dim]No commands in history.[/dim]")
            else:
                start = max(0, len(history) - 30)
                for i, h in enumerate(history[start:], start + 1):
                    console.print(f"  [dim]{i:3d}.[/dim] {h}")
        elif cmd in COMMAND_TREE:
            COMMAND_TREE[cmd]["handler"](cmd_args)
        elif cmd in GENERAL_COMMANDS:
            GENERAL_COMMANDS[cmd]["handler"](cmd_args)
        else:
            console.print(f"[yellow]Unknown: {cmd}[/yellow]")


def _build_context():
    from prompt_toolkit.formatted_text import FormattedText
    sess = load_session()
    proj = sess.get("last_project", "")
    proto = sess.get("last_protocol", "")

    parts = [("", "("), ("bold", "sci")]
    if proj:
        parts.append(("", " "))
        parts.append(("ansibrightgreen bold", proj))
    if proto:
        parts.append(("", " "))
        parts.append(("ansibrightcyan bold", proto))
    parts.append(("", ") "))
    return FormattedText(parts)


def _show_banner():
    console.print()
    console.print(Panel(
        f"[bold]sci[/bold] — Scientific Data Analysis CLI  [dim]v{__version__}[/dim]\n"
        "[dim]Type 'help' for commands, 'exit' to quit.[/dim]",
        border_style="green",
    ))
    console.print()


def _split_line(line: str) -> list[str]:
    import shlex
    try:
        return shlex.split(line)
    except ValueError:
        return line.split()

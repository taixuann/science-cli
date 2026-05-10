"""close command handler — clears session context (protocol)."""

from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag

console = Console()


def _parse_flags(args: list) -> tuple:
    positional = []
    flags = {}
    i = 0
    while i < len(args):
        a = args[i]
        if is_flag(a):
            key = a.lstrip("-")
            if i + 1 < len(args) and not is_flag(args[i + 1]):
                flags[key] = args[i + 1]
                i += 2
            else:
                flags[key] = True
                i += 1
        else:
            positional.append(a)
            i += 1
    return positional, flags


def close_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("close")
        return

    pos, flags = _parse_flags(args)
    mode = flags.get("m") or flags.get("mode", "")

    if mode != "protocol":
        console.print("[yellow]Usage: close -m protocol[/yellow]")
        return

    from science_cli.core.session import load_session, clear_last_protocol

    sess = load_session()
    was_active = sess.get("last_protocol", "")

    if not was_active:
        console.print("[dim]No protocol is currently open.[/dim]")
        return

    clear_last_protocol()

    rprint(f"[bold green]\u2713[/bold green] Closed protocol: [bold white]{was_active}[/bold white]")
    rprint("[dim]Session context cleared. Working at project level.[/dim]")

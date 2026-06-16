"""close command handler — close context with auto-save at step/protocol/project level."""

from rich.console import Console

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag

console = Console()


def _parse_flags(args: list) -> tuple:
    """Parse positional args and flags from command-line argument list."""
    positional = []
    flags: dict[str, str | bool] = {}
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
    """Handle `close` command — close context with auto-save.

    Modes:
        close -m step      — close current step, auto-save
        close -m protocol  — close current protocol, auto-save
        close -m project   — close current project, auto-save

    Each level saves current state before clearing the context pointer,
    so reopening the same project/protocol/step restores prior state.
    """
    if not args or args[0] in ("--help", "-h"):
        show_command_help("close")
        return

    pos, flags = _parse_flags(args)
    mode = flags.get("m") or flags.get("mode", "")

    if mode == "step":
        _close_step()
    elif mode == "protocol":
        _close_protocol()
    elif mode == "project":
        _close_project()
    else:
        console.print("[yellow]Usage: close -m step|protocol|project[/yellow]")
        return


def _close_step() -> None:
    """Close the current step — save state and clear last_step."""
    from science_cli.core.session import (
        load_session,
        save_session,
        save_step_state,
    )
    sess = load_session()
    current_step = sess.get("last_step", "")

    if not current_step:
        console.print("[yellow]No step currently open.[/yellow]")
        return

    # Save step-level state before clearing
    save_step_state()  # snapshots whatever is currently accumulated
    sess["last_step"] = ""
    save_session(sess)
    console.print(f"[bold green]✓[/bold green] Closed step: [bold white]{current_step}[/bold white]")


def _close_protocol() -> None:
    """Close the current protocol — save state and clear last_protocol + last_step."""
    from science_cli.core.session import (
        clear_protocol_state,
        load_session,
        save_context_state,
        save_session,
    )
    sess = load_session()
    current_protocol = sess.get("last_protocol", "")

    if not current_protocol:
        console.print("[yellow]No protocol currently open.[/yellow]")
        return

    # Save all context before clearing
    save_context_state()
    sess["last_protocol"] = ""
    sess["last_step"] = ""
    clear_protocol_state(sess)
    save_session(sess)
    console.print(f"[bold green]✓[/bold green] Closed protocol: [bold white]{current_protocol}[/bold white]")


def _close_project() -> None:
    """Close the current project — save state and clear all context."""
    from science_cli.core.session import (
        clear_project_state,
        load_session,
        save_context_state,
        save_session,
    )
    sess = load_session()
    current_project = sess.get("last_project", "")

    if not current_project:
        console.print("[yellow]No project currently open.[/yellow]")
        return

    # Save all context before clearing
    save_context_state()
    sess["last_project"] = ""
    sess["last_protocol"] = ""
    sess["last_step"] = ""
    clear_project_state(sess)
    save_session(sess)
    console.print(f"[bold green]✓[/bold green] Closed project: [bold white]{current_project}[/bold white]")

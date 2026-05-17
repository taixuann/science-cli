"""SCI REPL — interactive shell with TUI-style formatting (no full-screen).

Uses prompt_toolkit PromptSession in normal terminal mode. The banner is
printed once at startup. Each prompt re-prints session context + separators
above the input line, so context is always visible right above where you type.
No alternate screen — scrollback friendly.
"""

import io
import os
import sys
import shlex
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

from rich.console import Console as RichConsole

from science_cli import __version__
from science_cli.cli.commands import COMMAND_TREE
from science_cli.core.session import load_session, add_history, get_history
from science_cli.tui.banner import SCI_ART
from science_cli.cli.help import show_top_help, show_command_help

ACCENT = "#55ee77"
DIM = "#888888"
TEXT = "#cccccc"
PROJECT_COL = "#d4a853"
PROTOCOL_COL = "#5ea8b5"
TERM_WIDTH = 80


def _capture_handler_output(cmd_name: str, cmd_args: list[str]) -> str:
    """Run a COMMAND_TREE handler and capture all output to a string."""
    info = COMMAND_TREE.get(cmd_name)
    if not info:
        return f"Unknown command: {cmd_name}"
    handler = info["handler"]
    buf = io.StringIO()
    capture = RichConsole(file=buf, force_terminal=True, width=120, color_system="truecolor")
    mod = sys.modules.get(handler.__module__)
    saved = None
    if mod and hasattr(mod, "console"):
        saved = mod.console
        mod.console = capture
    try:
        handler(cmd_args)
    except SystemExit:
        pass
    except Exception as e:
        capture.print(f"[#d47a7a]{e}[/]")
    finally:
        if saved is not None:
            mod.console = saved
    return buf.getvalue()


def _capture_help_output(args: list[str]) -> str:
    """Capture help command output to a string."""
    buf = io.StringIO()
    c = RichConsole(file=buf, force_terminal=True, color_system="truecolor")
    mod = sys.modules.get("science_cli.cli.help")
    saved = getattr(mod, "console", None) if mod else None
    if saved is not None:
        mod.console = c
    try:
        if args:
            show_command_help(args[0])
        else:
            show_top_help()
    finally:
        if saved is not None:
            mod.console = saved
    return buf.getvalue()


def _build_context_prompt() -> FormattedText:
    """Build the multi-line prompt: separator + session info + separator + 'sci> '."""
    ft = FormattedText()
    sess = load_session()

    # top separator
    ft.append((DIM, "  " + "─" * (TERM_WIDTH - 4) + "\n"))

    # session info
    theme = sess.get("theme", "default")
    ft.append((DIM, "  theme: "))
    ft.append((TEXT, theme))
    ft.append((DIM, " │ ctx "))

    proj = sess.get("last_project", "")
    prot = sess.get("last_protocol", "")
    step = sess.get("last_step", "")
    if proj:
        ft.append((PROJECT_COL, proj))
    else:
        ft.append((DIM, "--"))
    if prot:
        ft.append((PROTOCOL_COL, f"/{prot}"))
    if step:
        ft.append((DIM, f"/{step}"))

    # bottom separator + prompt
    ft.append((DIM, "\n  " + "─" * (TERM_WIDTH - 4) + "\n"))
    ft.append((f"bold {ACCENT}", "sci> "))
    return ft


def _print_banner():
    """Print the SCI ASCII banner + version to stdout."""
    for line in SCI_ART.split("\n"):
        print(f"  \x1b[1m\x1b[38;2;85;238;119m{line}\x1b[0m")
    print(f"  \x1b[1m\x1b[38;2;85;238;119mscience-cli v{__version__}\x1b[0m")
    print()


def run_repl():
    """Launch the inline REPL with TUI-style context prompt."""
    hist_file = Path.home() / ".config" / "science-cli" / "repl_history"
    hist_file.parent.mkdir(parents=True, exist_ok=True)

    pt_style = Style([
        ("sci-prompt", f"bold {ACCENT}"),
    ])

    session = PromptSession(
        history=FileHistory(str(hist_file)),
        auto_suggest=AutoSuggestFromHistory(),
        style=pt_style,
    )

    _print_banner()

    while True:
        try:
            line = session.prompt(_build_context_prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        raw = line.strip()
        if not raw:
            continue

        add_history(raw)
        sep = "  " + "─" * (TERM_WIDTH - 4)
        print(f"\x1b[0m{sep}")
        print(f">>> {raw}")

        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = raw.split()

        cmd = parts[0]
        args = parts[1:]

        if cmd in ("exit", "quit"):
            break

        if cmd in ("clear", "cls"):
            os.system("clear")
            _print_banner()
            continue

        if cmd == "help":
            out = _capture_help_output(args)
            if out:
                for lo in out.split("\n"):
                    print(lo)
            print()
            continue

        if cmd == "history":
            history = get_history()
            if not history:
                print("(no history)")
            else:
                start = max(0, len(history) - 30)
                for i, h in enumerate(history[start:], start + 1):
                    print(f"  {i:3d}. {h}")
            print()
            continue

        if cmd == "version":
            print(f"sci version {__version__}")
            print()
            continue

        if cmd in COMMAND_TREE:
            out = _capture_handler_output(cmd, args)
            if out:
                for lo in out.split("\n"):
                    print(lo)
            print()
            continue

        print(f"Unknown: {cmd}")
        print()

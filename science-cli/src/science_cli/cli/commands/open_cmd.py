"""open command handler — sets session context (protocol)."""

import yaml
from pathlib import Path
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


def open_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("open")
        return

    pos, flags = _parse_flags(args)
    mode = flags.get("m") or flags.get("mode", "")

    if mode != "protocol":
        console.print("[yellow]Usage: open -m protocol -n <name>[/yellow]")
        return

    name = flags.get("n") or flags.get("name")
    if not name:
        console.print("[yellow]Required: -n / --name (protocol name)[/yellow]")
        return

    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return
    paths = ProjectPaths(proj)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    yaml_path = paths.protocol_yaml(safe_name)
    if not yaml_path.exists():
        console.print(f"[red]Protocol '{safe_name}' not found.[/red]")
        return

    with open(yaml_path) as f:
        protocol = yaml.safe_load(f) or {}

    from science_cli.core.session import set_last_protocol
    set_last_protocol(safe_name)

    steps = protocol.get("steps", [])
    rprint(f"\n[bold green]✓[/bold green] Opened protocol: [bold white]{safe_name}[/bold white]")
    rprint(f"  [dim]{protocol.get('description', '(no description)')}[/dim]\n")

    for s in steps:
        sn = s.get("name", "?")
        t = s.get("technique", "")
        tech_tag = f" [green]({t})[/green]" if t else ""
        sfiles = s.get("files", [])
        rprint(f"  [cyan]•[/cyan] {sn}{tech_tag}")
        if sfiles:
            for sf in sfiles:
                rprint(f"    [dim]{sf}[/dim]")

    rprint(f"\n[dim]Session context set to protocol '{safe_name}'.[/dim]")
    rprint("[dim]Plot/analyze commands will auto-reference this protocol's files.[/dim]")
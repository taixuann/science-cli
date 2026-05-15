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
    """Handle `open` command — set session context.

    Modes:
        open -m project <name>      — open a project (was 'project open <name>')
        open -m protocol -n <name>  — open a protocol (existing behavior)
        open -m step <step_id>      — open a specific step within current protocol
    """
    if not args or args[0] in ("--help", "-h"):
        show_command_help("open")
        return

    pos, flags = _parse_flags(args)
    mode = flags.get("m") or flags.get("mode", "")

    if mode == "project":
        name = flags.get("n") or flags.get("name", "")
        if not name and pos:
            name = pos[0]
        if not name:
            console.print("[yellow]Usage: open -m project <name> (or -n <name>)[/yellow]")
            return
        _open_project(name)
    elif mode == "step":
        if not pos:
            console.print("[yellow]Usage: open -m step <step_id>[/yellow]")
            return
        _open_step(pos[0])
    elif mode == "protocol":
        name = flags.get("n") or flags.get("name")
        if not name:
            console.print("[yellow]Required: -n / --name (protocol name)[/yellow]")
            return
        _open_protocol(name)
    else:
        console.print("[yellow]Usage: open -m project|protocol|step [flags][/yellow]")
        return


def _open_project(name: str) -> None:
    """Open a project and set session context with state restoration."""
    from science_cli.core.project import open_project, _get_projects_root
    from science_cli.core.session import (
        load_session,
        save_session,
        set_last_project,
        restore_context_state,
    )

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip().lower().replace(" ", "_")
    if not safe_name:
        console.print("[red]Invalid project name.[/red]")
        return

    proj_path = open_project(safe_name)
    if not proj_path:
        console.print(f"[red]Project '{safe_name}' not found.[/red]")
        rprint(f"[dim]Use 'ls -m project' to see available projects, or 'add -m project <name>' to create one.[/dim]")
        return

    set_last_project(safe_name)

    # Restore project-level state if available
    restore_context_state()

    # Show quick stats
    raw_dir = proj_path / "data" / "raw"
    proto_dir = proj_path / "protocol"
    n_raw = len(list(raw_dir.iterdir())) if raw_dir.exists() else 0
    n_proto = _count_protocol_yamls(proto_dir)

    rprint(f"\n[bold green]✓[/bold green] Opened project: [bold white]{safe_name}[/bold white]")
    rprint(f"  [dim]Path: {proj_path}[/dim]")
    rprint(f"  [dim]Raw files: {n_raw} | Protocols: {n_proto}[/dim]")
    rprint(f"\n[dim]Session context set to project '{safe_name}'.[/dim]")


def _open_protocol(name: str) -> None:
    """Open a protocol and set session context (existing behavior)."""
    import yaml
    from pathlib import Path

    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.session import set_last_protocol, restore_context_state

    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open. Use 'open -m project <name>' first.[/yellow]")
        return
    paths = ProjectPaths(proj)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    yaml_path = paths.protocol_yaml(safe_name)
    if not yaml_path.exists():
        console.print(f"[red]Protocol '{safe_name}' not found.[/red]")
        return

    with open(yaml_path) as f:
        protocol = yaml.safe_load(f) or {}

    set_last_protocol(safe_name)

    # ── Clear step context when opening a new protocol
    from science_cli.core.session import set_last_step
    set_last_step("")

    # Restore protocol-level state
    restore_context_state()

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


def _open_step(step_id: str) -> None:
    """Open a specific step within the current protocol."""
    import yaml
    from pathlib import Path

    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.session import load_session, set_last_step

    sess = load_session()
    current_protocol = sess.get("last_protocol", "")

    if not current_protocol:
        console.print("[yellow]No protocol open. Use 'open -m protocol -n <name>' first.[/yellow]")
        return

    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(current_protocol)
    if not yaml_path.exists():
        console.print(f"[red]Protocol '{current_protocol}' not found.[/red]")
        return

    with open(yaml_path) as f:
        protocol = yaml.safe_load(f) or {}

    steps = protocol.get("steps", [])
    step_names = [s.get("name", "") for s in steps]

    if step_id not in step_names:
        rprint(f"[yellow]Step '{step_id}' not found in protocol '{current_protocol}'.[/yellow]")
        rprint(f"[dim]Available steps: {', '.join(step_names)}[/dim]")
        return

    set_last_step(step_id)

    # Show step details
    for s in steps:
        if s.get("name") == step_id:
            t = s.get("technique", "")
            sfiles = s.get("files", [])
            rprint(f"\n[bold green]✓[/bold green] Opened step: [bold white]{step_id}[/bold white]")
            if t:
                rprint(f"  [dim]Technique: {t}[/dim]")
            rprint(f"  [dim]Files: {len(sfiles)}[/dim]")
            if sfiles:
                for sf in sfiles:
                    rprint(f"    [dim]• {sf}[/dim]")
            break

    rprint(f"\n[dim]Session context set to step '{step_id}' in protocol '{current_protocol}'.[/dim]")


def _count_protocol_yamls(proto_dir: object) -> int:
    """Count unique protocol YAMLs across new and legacy layouts."""
    from pathlib import Path as PPath
    if not isinstance(proto_dir, PPath):
        return 0
    if not proto_dir.exists():
        return 0
    found: set[str] = set()
    for sub in proto_dir.iterdir():
        if sub.is_dir():
            yaml_candidate = sub / f"{sub.name}.yaml"
            if yaml_candidate.exists():
                found.add(sub.name)
    for y in proto_dir.glob("*.yaml"):
        if y.stem not in found:
            found.add(y.stem)
    return len(found)
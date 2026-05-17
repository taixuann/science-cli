"""status command handler — show current context (project/protocol/step)."""

from pathlib import Path

import yaml
from rich import print as rprint
from rich.console import Console
from rich.table import Table

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


def status_handler(args: list) -> None:
    """Handle `status` command — show current context.

    Modes:
        status -m project   — show current project/protocol/step context
        status -m protocol  — show current protocol and step
        status              — show full context tree (project → protocol → step)

    Display is formatted in Rich tables with the current context entry highlighted.
    """
    if args and args[0] in ("--help", "-h"):
        show_command_help("status")
        return

    pos, flags = _parse_flags(args)
    mode = flags.get("m") or flags.get("mode", "")

    if mode == "project":
        _status_project()
    elif mode == "protocol":
        _status_protocol()
    else:
        _status_full()


def _status_full() -> None:
    """Show full context tree: project → all protocols → session step."""
    from science_cli.core.project import get_current_project_path, list_projects
    from science_cli.core.session import load_session
    sess = load_session()

    current_project = sess.get("last_project", "")
    current_protocol = sess.get("last_protocol", "")
    current_step = sess.get("last_step", "")

    # ── Project context ──
    rprint()
    proj = get_current_project_path()
    if current_project and proj:
        raw_dir = proj / "data" / "raw"
        n_raw = len(list(raw_dir.iterdir())) if raw_dir.exists() else 0
        proto_dir = proj / "protocol"
        n_proto = _count_protocol_yamls(proto_dir)
        rprint(f"[bold]Project:[/bold] [bold white]{current_project}[/bold white]  [dim]({n_raw} raw files, {n_proto} protocols)[/dim]")
    else:
        rprint("[yellow]No project open.[/yellow]")

    # ── Protocol context ──
    if current_protocol and proj:
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(proj)
        yaml_path = paths.protocol_yaml(current_protocol)
        if yaml_path.exists():
            with open(yaml_path) as f:
                proto = yaml.safe_load(f) or {}
            desc = proto.get("description", "(no description)")
            steps = proto.get("steps", [])
            table = Table(title=f"Protocol: {current_protocol}", border_style="cyan")
            table.add_column("Step", style="bold white")
            table.add_column("Technique", style="green")
            table.add_column("Files", justify="right", style="dim")
            for s in steps:
                sn = s.get("name", "?")
                t = s.get("technique", "")
                nf = len(s.get("files", []))
                marker = " [bold cyan]◀ current[/bold cyan]" if sn == current_step else ""
                table.add_row(f"{sn}{marker}", t, str(nf))
            console.print(table)
            rprint(f"  [dim]{desc}[/dim]")
        else:
            rprint(f"[yellow]Protocol '{current_protocol}' not found on disk.[/yellow]")
    elif current_protocol:
        rprint(f"[yellow]Protocol '{current_protocol}' set in session but project not found.[/yellow]")
    else:
        rprint("[dim]No protocol open.[/dim]")

    # ── All projects list ──
    projects = list_projects()
    if projects:
        rprint(f"\n[bold]All projects ({len(projects)}):[/bold]")
        for p in projects:
            marker = " [bold cyan]◀ current[/bold cyan]" if p == current_project else ""
            rprint(f"  [cyan]•[/cyan] {p}{marker}")

    rprint()


def _status_project() -> None:
    """Show project-level context: current project, protocol, step."""
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session

    sess = load_session()
    current_project = sess.get("last_project", "")
    current_protocol = sess.get("last_protocol", "")
    current_step = sess.get("last_step", "")

    rprint()
    if not current_project:
        rprint("[yellow]No project open. Use 'open -m project <name>' or 'add -m project <name>'.[/yellow]")
        return

    proj = get_current_project_path()
    if not proj:
        rprint(f"[red]Project '{current_project}' not found on disk.[/red]")
        return

    # Project-level metadata from session
    project_state = sess.get("project_state", {})

    table = Table(title="Project Context", border_style="cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value", style="white")

    table.add_row("Project", current_project)
    table.add_row("Path", str(proj))
    table.add_row("Protocol", current_protocol if current_protocol else "[dim](none)[/dim]")
    table.add_row("Step", current_step if current_step else "[dim](none)[/dim]")

    if project_state:
        for k, v in project_state.items():
            table.add_row(f"  metadata.{k}", str(v))

    # Project disk stats
    raw_dir = proj / "data" / "raw"
    table.add_row("Raw files", str(len(list(raw_dir.iterdir())) if raw_dir.exists() else 0))
    proto_dir = proj / "protocol"
    table.add_row("Protocols", str(_count_protocol_yamls(proto_dir)))

    console.print(table)
    rprint()


def _status_protocol() -> None:
    """Show protocol-level context: current protocol and step."""
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session

    sess = load_session()
    current_protocol = sess.get("last_protocol", "")
    current_step = sess.get("last_step", "")

    rprint()
    if not current_protocol:
        rprint("[yellow]No protocol open. Use 'open -m protocol -n <name>'.[/yellow]")
        return

    proj = get_current_project_path()
    if not proj:
        rprint("[yellow]No project found. Use 'open -m project <name>' first.[/yellow]")
        return

    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(current_protocol)

    if not yaml_path.exists():
        rprint(f"[red]Protocol '{current_protocol}' not found.[/red]")
        return

    with open(yaml_path) as f:
        proto = yaml.safe_load(f) or {}

    protocol_state = sess.get("protocol_state", {})

    table = Table(title=f"Protocol Context: {current_protocol}", border_style="cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value", style="white")

    table.add_row("Protocol", current_protocol)
    table.add_row("Description", proto.get("description", "(no description)"))
    table.add_row("Created", proto.get("created", "unknown"))
    table.add_row("Step", current_step if current_step else "[dim](none)[/dim]")

    if protocol_state:
        for k, v in protocol_state.items():
            table.add_row(f"  state.{k}", str(v))

    steps = proto.get("steps", [])
    table.add_row("Total steps", str(len(steps)))

    console.print(table)

    # Step table
    if steps:
        rprint()
        step_table = Table(title="Steps", border_style="dim cyan")
        step_table.add_column("Step", style="bold white")
        step_table.add_column("Technique", style="green")
        step_table.add_column("Files", justify="right", style="dim")
        for s in steps:
            sn = s.get("name", "?")
            t = s.get("technique", "")
            nf = len(s.get("files", []))
            marker = " [bold cyan]◀ current[/bold cyan]" if sn == current_step else ""
            step_table.add_row(f"{sn}{marker}", t, str(nf))
        console.print(step_table)

    rprint()


def _count_protocol_yamls(proto_dir: Path) -> int:
    """Count unique protocol YAMLs across new and legacy layouts."""
    if not proto_dir.exists():
        return 0
    found: set[str] = set()
    # New format: protocol/<name>/<name>.yaml
    for sub in proto_dir.iterdir():
        if sub.is_dir():
            yaml_candidate = sub / f"{sub.name}.yaml"
            if yaml_candidate.exists():
                found.add(sub.name)
    # Legacy format: protocol/<name>.yaml (only if no new-format entry)
    for y in proto_dir.glob("*.yaml"):
        if y.stem not in found:
            found.add(y.stem)
    return len(found)

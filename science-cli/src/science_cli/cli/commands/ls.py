"""ls command handler — list protocols/steps/files (global, not session-bound)."""

import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
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


def ls_handler(args: list) -> None:
    if args and args[0] in ("--help", "-h"):
        show_command_help("ls")
        return

    pos, flags = _parse_flags(args)

    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open. Use 'project open <name>' first.[/yellow]")
        return

    show_all = flags.get("all", False)
    show_step = flags.get("step", False)
    show_files = flags.get("files", False)
    mode = flags.get("m") or flags.get("mode", "")

    if mode == "protocol" or show_all or show_step or show_files:
        _ls_protocol(proj, show_all=show_all, show_step=show_step, show_files=show_files)
    elif pos:
        _ls_step(proj, pos[0])
    else:
        _ls_default(proj)


def _ls_default(proj: Path) -> None:
    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    if not proto_yamls:
        rprint(f"[yellow]No protocols found.[/yellow]")
        return

    table = Table(title="Protocols", border_style="cyan")
    table.add_column("Name", style="bold white")
    table.add_column("Steps", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Description", style="dim")

    for py in proto_yamls:
        with open(py) as f:
            data = yaml.safe_load(f) or {}
        steps = data.get("steps", [])
        n_files = sum(len(s.get("files", [])) for s in steps)
        table.add_row(py.stem, str(len(steps)), str(n_files), data.get("description", ""))

    console.print(table)
    rprint(f"\n[dim]Use 'ls -m protocol --all' for full view.[/dim]")


def _device_crossref(step_dir: Path) -> str:
    """Read devices.yaml and return a summary string, or empty string."""
    devices_yaml = step_dir / "devices.yaml"
    if not devices_yaml.exists():
        return ""
    try:
        with open(devices_yaml) as f:
            dd = yaml.safe_load(f) or {}
        pts = dd.get("points", [])
        coverage: dict[str, int] = {}
        for pt in pts:
            for tech in (pt.get("techniques") or {}):
                coverage[tech] = coverage.get(tech, 0) + 1
        total = len(pts)
        dev = dd.get("device", {})
        dims = f"{dev.get('rows', '?')}x{dev.get('cols', '?')}"
        cov_str = ", ".join(f"{t}:{c}" for t, c in sorted(coverage.items()))
        return f" [dim]← {dims} {total}pts [{cov_str}][/dim]"
    except Exception:
        return ""


def _ls_protocol(proj: Path, show_all: bool = False, show_step: bool = False, show_files: bool = False) -> None:
    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    if not proto_yamls:
        rprint(f"[yellow]No protocols found.[/yellow]")
        return

    for py in proto_yamls:
        with open(py) as f:
            data = yaml.safe_load(f) or {}
        steps = data.get("steps", [])

        rprint(f"\n[bold white]{py.stem}[/bold white] — [dim]{data.get('description', '(no desc)')}[/dim]")

        for s in steps:
            sn = s.get("name", "?")
            t = s.get("technique", "")
            tech_tag = f" [green]({t})[/green]" if t else ""
            sfiles = s.get("files", [])

            step_dir = paths.protocol_subdir(py.stem) / sn
            cref = _device_crossref(step_dir) if step_dir.exists() else ""

            if show_step:
                rprint(f"  [cyan]•[/cyan] {sn}{tech_tag}{cref}")
            elif show_files or show_all:
                rprint(f"  [cyan]•[/cyan] {sn}{tech_tag}{cref}")
                if sfiles:
                    for sf in sfiles:
                        rprint(f"    [dim]  {sf}[/dim]")
            if show_all:
                if step_dir.exists():
                    extra = sorted(step_dir.glob("*"))
                    extra_names = [e.name for e in extra if e.name not in sfiles and e.name != "results"]
                    for en in extra_names:
                        rprint(f"    [dim]  {en} (in dir)[/dim]")


def _ls_step(proj: Path, step_name: str) -> None:
    proto_dir = proj / "protocol"
    
    # Step directories are now scoped under protocol/<proto_name>/<step_name>.
    # Search across all protocol subdirectories.
    matches: list[tuple[str, Path]] = []
    if proto_dir.exists():
        for proto_subdir in sorted(proto_dir.iterdir()):
            if proto_subdir.is_dir() and not proto_subdir.name.endswith(".yaml"):
                candidate = proto_subdir / step_name
                if candidate.exists():
                    matches.append((proto_subdir.name, candidate))
    
    if not matches:
        rprint(f"[red]Step '{step_name}' not found in any protocol.[/red]")
        return
    
    for proto_name, step_dir in matches:
        files = sorted(step_dir.iterdir())
        if not files:
            rprint(f"[yellow]No files in '{proto_name}/{step_name}'.[/yellow]")
            continue
        
        prefix = (
            f"[bold white]{proto_name}/{step_name}[/bold white]"
            if len(matches) > 1
            else f"[bold white]{step_name}[/bold white]"
        )
        rprint(f"\n{prefix}")
        for f in files:
            if f.name == "results":
                continue
            rprint(f"  [dim]• {f.name}[/dim]")
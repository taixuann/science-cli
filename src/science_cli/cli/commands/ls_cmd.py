"""ls command handler — list protocols/steps/files (global, not session-bound)."""

import json
from pathlib import Path

import yaml
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag

console = Console()


def _fmt_desc(desc: str) -> str:
    """Flatten multiline descriptions for table cell display."""
    if not desc:
        return desc
    return desc.replace("\n", " ↵ ")


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
    if any(a in ("--help", "-h") for a in args):
        show_command_help("ls")
        return

    pos, flags = _parse_flags(args)
    mode = flags.get("m") or flags.get("mode", "")
    use_json = flags.get("json", False)

    # -m project works globally — no project context required
    if mode == "project":
        if use_json:
            print(json.dumps(_ls_projects_json(), indent=2, default=str))
        else:
            _ls_projects()
        return

    # F4: Remove ls -m file — guide user to workflow
    if mode == "file":
        console.print("[yellow]Use 'open -m step <step_name>' first to select a step, then run 'ls' to see files.[/yellow]")
        return

    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session

    proj = get_current_project_path()
    sess = load_session()

    # Extract explicit step name (-n / --name or positional)
    step_name = flags.get("n") or flags.get("name", "")
    if not step_name and pos:
        step_name = pos[0]

    # If step name given, skip context-aware and go directly
    if step_name and not mode:
        if not proj:
            console.print("[yellow]No project open. Use 'open -m project <name>' first.[/yellow]")
            return
        if use_json:
            print(json.dumps(_ls_step_json(proj, step_name), indent=2, default=str))
        else:
            _ls_step(proj, step_name)
        return

    # F1: Context-aware detection when no explicit mode or positional arg
    if not mode and not step_name:
        last_step = sess.get("last_step", "")
        last_protocol = sess.get("last_protocol", "")
        last_project = sess.get("last_project", "")

        if last_step and proj:
            if use_json:
                print(json.dumps(_ls_step_json(proj, last_step), indent=2, default=str))
            else:
                console.print(f"[dim]── Showing files in step '{last_step}' (context-aware) ──[/dim]")
                _ls_step(proj, last_step)
            return
        elif last_protocol and proj:
            if use_json:
                print(json.dumps(_ls_protocol_json(proj), indent=2, default=str))
            else:
                console.print(f"[dim]── Showing steps for protocol '{last_protocol}' (context-aware) ──[/dim]")
                _ls_default(proj)
            return
        elif last_project and proj:
            if use_json:
                print(json.dumps(_ls_protocol_json(proj), indent=2, default=str))
            else:
                console.print(f"[dim]── Showing protocols in project '{last_project}' (context-aware) ──[/dim]")
                _ls_default(proj)
            return
        else:
            if use_json:
                print(json.dumps(_ls_projects_json(), indent=2, default=str))
            else:
                _ls_projects()
            return

    if not proj:
        console.print("[yellow]No project open. Use 'open -m project <name>' or 'add -m project <name>' first.[/yellow]")
        return

    show_all = flags.get("all", False)
    show_step = flags.get("step", False)
    show_files = flags.get("files", False)

    step_name = flags.get("n") or flags.get("name", "")
    if not step_name and pos:
        step_name = pos[0]

    if mode == "protocol" or show_all or show_step or show_files:
        if use_json:
            print(json.dumps(_ls_protocol_json(proj), indent=2, default=str))
        else:
            _ls_protocol(proj, show_all=show_all, show_step=show_step, show_files=show_files)
    elif step_name:
        if use_json:
            print(json.dumps(_ls_step_json(proj, step_name), indent=2, default=str))
        else:
            _ls_step(proj, step_name)
    else:
        if use_json:
            print(json.dumps(_ls_protocol_json(proj), indent=2, default=str))
        else:
            _ls_default(proj)


def _ls_default(proj: Path) -> None:
    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    if not proto_yamls:
        rprint("[yellow]No protocols found.[/yellow]")
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
        table.add_row(py.stem, str(len(steps)), str(n_files), _fmt_desc(data.get("description", "")))

    console.print(table)
    rprint("\n[dim]Use 'ls -m protocol --all' for full view.[/dim]")


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
        rprint("[yellow]No protocols found.[/yellow]")
        return

    for py in proto_yamls:
        with open(py) as f:
            data = yaml.safe_load(f) or {}
        steps = data.get("steps", [])
        desc = data.get("description", "(no desc)")

        # F3: Rich Table with bold title and cyan border
        table = Table(title=f"Protocol: {py.stem}", border_style="cyan", show_lines=True)
        table.add_column("Step", style="bold white")
        table.add_column("Technique", style="green")
        table.add_column("Device", style="yellow")
        table.add_column("Files", style="dim", justify="right")
        table.add_column("Description", style="bright_black")

        def _file_name(f):
            return f["file"] if isinstance(f, dict) else str(f)

        for s in steps:
            sn = s.get("name", "?")
            t = s.get("technique", "")
            d = s.get("device", "")
            sfiles = s.get("files", [])
            n_files = len(sfiles)
            file_badge = f"{n_files} files" if n_files else "—"
            sdesc = s.get("description", "")
            sparams = s.get("params", {})

            step_dir = paths.protocol_subdir(py.stem) / sn
            cref = _device_crossref(step_dir) if step_dir.exists() else ""

            # Show extra files from directory when show_all
            if show_all and step_dir.exists():
                extra = sorted(step_dir.glob("*"))
                sfile_names = {_file_name(f) for f in sfiles}
                extra_names = [e.name for e in extra if e.name not in sfile_names and e.name != "results"]
                if extra_names:
                    file_badge += f" +{len(extra_names)} in dir"

            display_desc = _fmt_desc(sdesc)
            if sparams:
                param_str = ", ".join(f"{k}: {v}" for k, v in sparams.items())
                display_desc = (display_desc + " | " + param_str) if display_desc else param_str
            if show_step or show_files or show_all:
                # Include file list in description column for detailed views
                if sfiles:
                    names = [_file_name(f) for f in sfiles[:3]]
                    details = ", ".join(names)
                    if len(sfiles) > 3:
                        details += f" +{len(sfiles) - 3} more"
                    if display_desc:
                        display_desc += f"  [{details}]"
                    else:
                        display_desc = details

            dev_display = d or "—"
            table.add_row(sn, t, dev_display, file_badge, display_desc)

        console.print(table)
        console.print(f"  [dim]{desc}[/dim]")
        console.print()


def _fmt_size_ls(bytes: int) -> str:
    """Format file size for display (local helper)."""
    if bytes < 1024:
        return f"{bytes}B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.0f}KB"
    else:
        return f"{bytes / 1024 ** 2:.1f}MB"


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
        # Filter out 'results' subdirectory
        display_files = [f for f in files if f.name != "results"]
        if not display_files:
            rprint(f"[yellow]No files in '{proto_name}/{step_name}'.[/yellow]")
            continue

        title = f"Step: {proto_name}/{step_name}" if len(matches) > 1 else f"Step: {step_name}"

        # F3: Rich Table with bold title and cyan border
        table = Table(title=title, border_style="cyan", show_lines=True)
        table.add_column("File", style="dim")
        table.add_column("Size", justify="right", style="dim")

        for f in display_files:
            size = f.stat().st_size
            table.add_row(f.name, _fmt_size_ls(size))

        console.print(table)
        console.print()


def _ls_projects() -> None:
    """List all projects in the configured projects root directory.

    Works globally — does not require a project to be open.
    """
    from science_cli.core.project import get_current_project_path, list_projects
    from science_cli.core.session import load_session

    projects = list_projects()

    if not projects:
        rprint("[yellow]No projects found.[/yellow]")
        return

    current = load_session().get("last_project", "")
    proj = get_current_project_path()

    table = Table(title="Projects", border_style="cyan")
    table.add_column("Project", style="bold white")
    table.add_column("Path", style="dim")
    table.add_column("Status", style="green")

    for p in projects:
        is_current = p == current
        marker = "[bold cyan]◀ current[/bold cyan]" if is_current else ""
        path_info = str(proj.parent / p) if proj and is_current else ""

        # Quick stats for each project
        from science_cli.core.project import _get_projects_root
        root = _get_projects_root()
        candidate = root / p

        n_raw = 0
        n_proto = 0
        if candidate.exists():
            raw_dir = candidate / "data" / "raw"
            n_raw = len(list(raw_dir.iterdir())) if raw_dir.exists() else 0
            proto_dir = candidate / "protocol"
            n_proto = _count_protocol_yamls_local(proto_dir)

        status_str = f"{n_raw} raw, {n_proto} protocols"
        table.add_row(
            f"{p} {marker}" if is_current else p,
            str(path_info) if path_info else "",
            status_str,
        )

    console.print(table)
    rprint()


def _count_protocol_yamls_local(proto_dir: Path) -> int:
    """Count unique protocol YAMLs (local helper to avoid circular imports)."""
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


def _ls_projects_json() -> list[dict]:
    from science_cli.core.project import _get_projects_root, get_current_project_path, list_projects
    from science_cli.core.session import load_session

    projects = list_projects()
    current = load_session().get("last_project", "")
    proj = get_current_project_path()
    root = _get_projects_root()

    result: list[dict] = []
    for p in projects:
        entry: dict = {"name": p, "current": p == current}
        candidate = root / p
        if candidate.exists():
            entry["path"] = str(candidate)
            raw_dir = candidate / "data" / "raw"
            entry["raw_file_count"] = len(list(raw_dir.iterdir())) if raw_dir.exists() else 0
            proto_dir = candidate / "protocol"
            entry["protocol_count"] = _count_protocol_yamls_local(proto_dir)
        result.append(entry)
    return result


def _ls_protocol_json(proj: Path) -> list[dict]:
    from science_cli.core.paths import ProjectPaths

    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    result: list[dict] = []

    for py in proto_yamls:
        with open(py) as f:
            data = yaml.safe_load(f) or {}
        steps = data.get("steps", [])
        step_entries: list[dict] = []
        for s in steps:
            if not isinstance(s, dict):
                continue
            sfiles = s.get("files", [])
            file_names = [f["file"] if isinstance(f, dict) else str(f) for f in sfiles]
            step_entries.append({
                "name": s.get("name", "?"),
                "technique": s.get("technique", ""),
                "device": s.get("device", ""),
                "file_count": len(sfiles),
                "files": file_names,
            })
        result.append({
            "name": py.stem,
            "description": data.get("description", ""),
            "device": data.get("device", {}),
            "step_count": len(steps),
            "steps": step_entries,
        })
    return result


def _ls_step_json(proj: Path, step_name: str) -> list[dict]:
    proto_dir = proj / "protocol"
    results: list[dict] = []

    if proto_dir.exists():
        for proto_subdir in sorted(proto_dir.iterdir()):
            if proto_subdir.is_dir() and not proto_subdir.name.endswith(".yaml"):
                candidate = proto_subdir / step_name
                if candidate.exists():
                    files = []
                    for f in sorted(candidate.iterdir()):
                        if f.name == "results":
                            continue
                        files.append({
                            "name": f.name,
                            "size": f.stat().st_size,
                        })
                    results.append({
                        "protocol": proto_subdir.name,
                        "step": step_name,
                        "files": files,
                    })
    return results

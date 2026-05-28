"""info command — machine-readable project manifest for AI agents."""

import json
from pathlib import Path

import yaml

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag


def _parse_flags(args: list) -> tuple:
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


def info_handler(args: list) -> None:
    if args and args[0] in ("--help", "-h"):
        show_command_help("info")
        return

    _pos, flags = _parse_flags(args)
    use_json = flags.get("json", False)

    data = _build_manifest()
    if not data:
        print(json.dumps({"error": "No project open"}, indent=2))
        return

    if use_json:
        print(json.dumps(data, indent=2, default=str))
    else:
        _print_human(data)


def _build_manifest() -> dict | None:
    """Build complete project manifest for AI agents."""
    from science_cli import __version__
    from science_cli.core.config import list_global_devices, list_global_techniques
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session
    from science_cli.theme.registry import list_themes

    proj = get_current_project_path()
    sess = load_session()

    manifest: dict = {
        "science_cli_version": __version__,
        "project": None,
        "session": {
            "last_project": sess.get("last_project", ""),
            "last_protocol": sess.get("last_protocol", ""),
            "last_step": sess.get("last_step", ""),
            "theme": sess.get("theme", "publication-nature"),
        },
        "protocols": [],
        "themes": list_themes(),
        "techniques": [],
    }

    if not proj:
        return manifest

    paths = ProjectPaths(proj)

    manifest["project"] = {
        "name": proj.name,
        "path": str(proj),
        "theme": sess.get("theme", "publication-nature"),
    }

    raw_dir = proj / "data" / "raw"
    if raw_dir.exists():
        manifest["project"]["raw_file_count"] = len(list(raw_dir.iterdir()))

    proto_yamls = paths.list_protocol_yamls()
    manifest["project"]["protocol_count"] = len(proto_yamls)

    for py in proto_yamls:
        try:
            with open(py) as f:
                proto = yaml.safe_load(f) or {}
        except Exception:
            continue

        if not isinstance(proto, dict):
            continue

        steps = proto.get("steps", [])
        device = proto.get("device", {})

        proto_entry: dict = {
            "name": py.stem,
            "description": proto.get("description", ""),
            "device": device if device else None,
            "step_count": len(steps),
            "steps": [],
        }

        proto_subdir = paths.protocol_subdir(py.stem)

        for s in steps:
            if not isinstance(s, dict):
                continue
            sn = s.get("name", "?")
            sfiles = s.get("files", [])

            file_entries: list[dict] = []
            for f in sfiles:
                fname = f["file"] if isinstance(f, dict) else str(f)
                fpath = proto_subdir / sn / fname
                file_entry: dict = {
                    "name": fname,
                    "path": str(fpath.relative_to(proj)) if fpath.exists() else "",
                }
                if isinstance(f, dict):
                    for ek in ("sweep_order", "sweep_type", "sweep", "temperature"):
                        if ek in f:
                            file_entry[ek] = f[ek]
                if fpath.exists():
                    file_entry["size"] = fpath.stat().st_size
                technique = _detect_technique_file(fname)
                if technique:
                    file_entry["technique"] = technique
                file_entries.append(file_entry)

            proto_entry["steps"].append({
                "name": sn,
                "technique": s.get("technique", ""),
                "device": s.get("device", ""),
                "description": s.get("description", ""),
                "file_count": len(sfiles),
                "files": file_entries,
            })

        manifest["protocols"].append(proto_entry)

    manifest["plot_hints"] = _technique_hints_dict()

    try:
        manifest["techniques"] = [
            {"slug": t, "devices": []} for t in list_global_techniques()
        ]
    except Exception:
        pass

    return manifest


def _technique_hints_dict() -> dict:
    from science_cli.cli.commands.plot import TECHNIQUE_HINTS

    result: dict = {}
    for tech, info in TECHNIQUE_HINTS.items():
        if isinstance(info, dict):
            result[tech] = {
                "plot_style": info.get("plot_style", ""),
                "figure": info.get("figure", ""),
            }
    return result


def _detect_technique_file(filename: str) -> str:
    from science_cli.core.technique import detect_technique

    t = detect_technique(filename)
    return t.lower() if t else ""


def _print_human(data: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()

    proj = data.get("project") or {}
    session = data.get("session", {})
    if proj:
        console.print(f"\n[bold]Project:[/bold] [bold white]{proj.get('name', '')}[/bold white]")
        console.print(f"  Path: [dim]{proj.get('path', '')}[/dim]")
        console.print(f"  Theme: [cyan]{session.get('theme', '')}[/cyan]")

    if session:
        console.print(f"\n[bold]Session Context:[/bold]")
        console.print(f"  Project:  {session['last_project'] or '[dim](none)[/dim]'}")
        console.print(f"  Protocol: {session['last_protocol'] or '[dim](none)[/dim]'}")
        console.print(f"  Step:     {session['last_step'] or '[dim](none)[/dim]'}")

    for proto in data.get("protocols", []):
        table = Table(title=f"Protocol: {proto['name']}", border_style="cyan")
        table.add_column("Step", style="bold white")
        table.add_column("Technique", style="green")
        table.add_column("Device", style="yellow")
        table.add_column("Files", justify="right", style="dim")
        for s in proto.get("steps", []):
            table.add_row(s["name"], s.get("technique", ""), s.get("device", ""), str(s["file_count"]))
        console.print(table)

    themes = data.get("themes", [])
    if themes:
        console.print(f"\n[bold]Themes:[/bold] {', '.join(themes)}")

    console.print()

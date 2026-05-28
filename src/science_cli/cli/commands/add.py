"""add command handler — protocol, metadata, data."""

from datetime import datetime
from pathlib import Path

import yaml
from rich import print as rprint
from rich.console import Console

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


def add_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("add")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "-m":
        if not sub_args:
            console.print("[yellow]Usage: add -m protocol|metadata|data [flags][/yellow]")
            return
        mode = sub_args[0]
        mode_args = sub_args[1:]

        if mode == "project":
            _add_project(mode_args)
        elif mode == "protocol":
            _add_protocol(mode_args)
        elif mode == "metadata":
            _add_metadata(mode_args)
        elif mode == "data":
            _add_data(mode_args)
        else:
            console.print(f"[yellow]Unknown add mode: {mode}[/yellow]")
    else:
        console.print(f"[yellow]Unknown add subcommand: {sub}[/yellow]")


def _add_project(args: list) -> None:
    """Create a new project — 'add -m project <name>' (was 'project create')."""
    _, flags = _parse_flags(args)
    name = flags.get("n") or flags.get("name")
    if not name:
        # If no -n flag, try positional argument
        if args and not args[0].startswith("-"):
            name = args[0]
        else:
            console.print("[yellow]Usage: add -m project <name>[/yellow]")
            return

    from science_cli.core.paths import sanitize_project_name
    from science_cli.core.project import _get_projects_root
    from science_cli.core.session import set_last_project
    safe_name = sanitize_project_name(name).strip().lower().replace(" ", "_")
    if not safe_name:
        console.print("[red]Invalid project name.[/red]")
        return

    projects_root = _get_projects_root()
    project_path = projects_root / safe_name
    if project_path.exists():
        console.print(f"[yellow]Project '{safe_name}' already exists.[/yellow]")
        return

    dirs = [
        project_path / "data" / "raw",
        project_path / "data" / "processed",
        project_path / "protocol",
        project_path / "results",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Create initial sci-config.yaml
    _create_default_config(project_path)

    # Set project context
    set_last_project(safe_name)

    console.print(f"[bold green]✓[/bold green] Created project: [bold white]{safe_name}[/bold white]")
    rprint(f"  [dim]Path: {project_path}[/dim]")
    rprint("  [dim]Directories: data/raw, data/processed, protocol, results[/dim]")


def _create_default_config(project_path: Path) -> None:
    """Create a minimal sci-config.yaml in the new project."""
    config_path = project_path / "sci-config.yaml"
    if config_path.exists():
        return
    import yaml
    default_config = {
        "description": f"Project: {project_path.name}",
        "techniques": {},
        "defaults": {},
    }
    with open(config_path, "w") as f:
        yaml.dump(default_config, f, default_flow_style=False)


def _add_protocol(args: list) -> None:
    _, flags = _parse_flags(args)

    name = flags.get("n") or flags.get("name")
    if not name:
        console.print("[yellow]Required: -n / --name (protocol name)[/yellow]")
        return

    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open. Use 'add -m project <name>' to create one, or 'open -m project <name>' to open one.[/yellow]")
        return

    from science_cli.core.paths import sanitize_protocol_name
    safe_name = sanitize_protocol_name(name)
    paths = ProjectPaths(proj)
    paths.protocol_dir.mkdir(parents=True, exist_ok=True)

    yaml_path = paths.protocol_yaml_new(safe_name)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    if yaml_path.exists():
        import questionary
        if not questionary.confirm(f"Protocol '{safe_name}' exists. Overwrite?", default=False).ask():
            return

    desc = flags.get("desc") or flags.get("description", "")
    steps_raw = flags.get("step", "")
    techs_raw = flags.get("t") or flags.get("technique", "")
    devs_raw = flags.get("d") or flags.get("device", "")

    steps = []
    if steps_raw:
        step_names = [s.strip() for s in steps_raw.split(",") if s.strip()]
        techs = [t.strip() for t in techs_raw.split(",") if t.strip()] if techs_raw else []
        devs = [d.strip() for d in devs_raw.split(",") if d.strip()] if devs_raw else []
        for i, sn in enumerate(step_names):
            entry = {"name": sn}
            if i < len(techs):
                entry["technique"] = techs[i]
            if i < len(devs):
                entry["device"] = devs[i]
            steps.append(entry)
            step_dir = paths.step_dir(safe_name, sn)
            step_dir.mkdir(parents=True, exist_ok=True)
            (step_dir / "results").mkdir(parents=True, exist_ok=True)

    protocol = {
        "name": safe_name,
        "description": desc,
        "created": datetime.now().isoformat(),
        "steps": steps,
    }

    with open(yaml_path, "w") as f:
        yaml.dump(protocol, f, default_flow_style=False, sort_keys=False)

    rprint(f"[bold green]✓[/bold green] Protocol '{safe_name}' created: {yaml_path}")
    if steps:
        rprint(f"  [dim]Steps: {', '.join(s['name'] for s in steps)}[/dim]")


def _add_metadata(args: list) -> None:
    _, flags = _parse_flags(args)

    steps_raw = flags.get("step")
    protocol_name = flags.get("pt") or flags.get("protocol")
    techs_raw = flags.get("t") or flags.get("technique")
    devs_raw = flags.get("d") or flags.get("device")

    if not steps_raw:
        console.print("[yellow]Required: --step (step ID(s), comma-separated)[/yellow]")
        return
    if not protocol_name:
        from science_cli.core.session import load_session
        protocol_name = load_session().get("last_protocol", "")
    if not protocol_name:
        console.print("[yellow]Required: -pt / --protocol (protocol name), or open a protocol first[/yellow]")
        return

    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    from science_cli.core.paths import sanitize_protocol_name
    safe_name = sanitize_protocol_name(protocol_name)
    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(safe_name)
    if not yaml_path.exists():
        console.print(f"[red]Protocol '{safe_name}' not found.[/red]")
        return

    with open(yaml_path) as f:
        protocol = yaml.safe_load(f) or {}

    step_names = [s.strip() for s in steps_raw.split(",") if s.strip()]
    techs = [t.strip() for t in techs_raw.split(",") if t.strip()] if techs_raw else []
    devs = [d.strip() for d in devs_raw.split(",") if d.strip()] if devs_raw else []

    existing = {s["name"]: s for s in protocol.get("steps", [])}
    for i, sn in enumerate(step_names):
        if sn in existing:
            if i < len(techs):
                existing[sn]["technique"] = techs[i]
            if i < len(devs):
                existing[sn]["device"] = devs[i]
        else:
            entry = {"name": sn}
            if i < len(techs):
                entry["technique"] = techs[i]
            if i < len(devs):
                entry["device"] = devs[i]
            protocol.setdefault("steps", []).append(entry)
        step_dir = paths.step_dir(safe_name, sn)
        step_dir.mkdir(parents=True, exist_ok=True)
        (step_dir / "results").mkdir(parents=True, exist_ok=True)

    with open(yaml_path, "w") as f:
        yaml.dump(protocol, f, default_flow_style=False, sort_keys=False)

    parts = [f"steps: {', '.join(step_names)}"]
    if techs:
        parts.append(f"techniques: {', '.join(techs)}")
    if devs:
        parts.append(f"devices: {', '.join(devs)}")
    rprint(f"[bold green]✓[/bold green] Metadata updated for '{safe_name}'")
    rprint(f"  [dim]{' | '.join(parts)}[/dim]")


def _add_data(args: list) -> None:
    _, flags = _parse_flags(args)

    use_all = flags.get("all", False)

    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    raw_dir = proj / "data" / "raw"
    if not raw_dir.exists():
        console.print("[red]data/raw/ not found in project.[/red]")
        return

    files = sorted(raw_dir.iterdir())
    if not files:
        console.print("[yellow]No files in data/raw/[/yellow]")
        return

    # Resolve protocol first (before file listing)
    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    if not proto_yamls:
        console.print("[yellow]No protocol YAMLs found.[/yellow]")
        return

    from science_cli.core.session import load_session, set_last_protocol
    sess = load_session()
    proto_name = sess.get("last_protocol", "")

    if proto_name:
        yaml_path = paths.protocol_yaml(proto_name)
        if not yaml_path.exists():
            proto_name = ""

    if not proto_name:
        from science_cli.core.fzf_utils import fzf_select as fzf_proto
        proto_names = [p.stem for p in proto_yamls]
        proto_choice = fzf_proto(proto_names, prompt="Select protocol:", multi=False)
        if not proto_choice:
            console.print("[yellow]No protocol selected.[/yellow]")
            return
        proto_name = proto_choice[0]
        set_last_protocol(proto_name)
    else:
        rprint(f"[dim]Using open protocol: {proto_name}[/dim]")

    yaml_path = paths.protocol_yaml(proto_name)
    with open(yaml_path) as f:
        protocol = yaml.safe_load(f) or {}

    step_names = [s["name"] for s in protocol.get("steps", [])]
    if not step_names:
        console.print("[yellow]No steps in protocol. Add steps first.[/yellow]")
        return

    # Build set of already-assigned files
    assigned_files: dict[str, str] = {}
    for s in protocol.get("steps", []):
        for fe in s.get("files", []):
            fname = fe["file"] if isinstance(fe, dict) else fe
            assigned_files[fname] = s["name"]

    # Build fzf display items with assignment markers
    from science_cli.core.fzf_utils import fzf_select

    item_names = [f.name for f in files]

    # F2: Group files — unassigned first, then per-step groups
    unassigned = sorted([n for n in item_names if n not in assigned_files])
    assigned_grouped: dict[str, list[str]] = {}
    for name in item_names:
        if name in assigned_files:
            step = assigned_files[name]
            assigned_grouped.setdefault(step, []).append(name)

    from science_cli.core.fzf_utils import build_fzf_display
    display_items: list[str] = []
    # Unassigned files (use "-" placeholder step)
    for name in unassigned:
        display_items.append(build_fzf_display(proto_name, "-", name, show_protocol=False))
    # Per-step sections
    for step in sorted(assigned_grouped.keys()):
        for fname in sorted(assigned_grouped[step]):
            display_items.append(build_fzf_display(proto_name, step, fname, show_protocol=False))

    import re
    selected = fzf_select(
        items=display_items,
        prompt=f"{proto_name} | Select files (Tab to multi-select):",
        multi=True,
    )
    if not selected:
        console.print("[yellow]No files selected.[/yellow]")
        return

    # Strip step column to recover filenames
    col_re = re.compile(r"^\S+\s+")
    selected_stripped: list[str] = []
    for s in selected:
        fname = col_re.sub("", s).strip()
        if fname:
            selected_stripped.append(fname)
    selected = selected_stripped

    # Build step choices with file count indicators
    step_counts: dict[str, int] = {}
    for s in protocol.get("steps", []):
        step_counts[s["name"]] = len(s.get("files", []))

    import questionary

    def _build_choices():
        choices = []
        for s in protocol.get("steps", []):
            sn = s["name"]
            t = s.get("technique", "")
            count = step_counts.get(sn, 0)
            label = sn
            if t:
                label += f" ({t})"
            label += f" \u2014 {count} files"
            choices.append(questionary.Choice(title=label, value=sn))
        choices.append(questionary.Choice(title="Skip", value="__skip__"))
        return choices

    if use_all:
        step_choice = questionary.select(
            f"Assign all {len(selected)} file(s) to which step?",
            choices=_build_choices(),
        ).ask()
        if not step_choice or step_choice == "__skip__":
            console.print("[yellow]Cancelled.[/yellow]")
            return
        steps_to_assign = {fname: step_choice for fname in selected}
    else:
        steps_to_assign = {}
        for filename in selected:
            step_choice = questionary.select(
                f"Assign '{filename}' to which step?",
                choices=_build_choices(),
            ).ask()
            if not step_choice or step_choice == "__skip__":
                continue
            steps_to_assign[filename] = step_choice

    for filename, step_choice in steps_to_assign.items():
        step_dir = paths.step_dir(proto_name, step_choice)
        step_dir.mkdir(parents=True, exist_ok=True)
        (step_dir / "results").mkdir(parents=True, exist_ok=True)

        src = raw_dir / filename
        link = step_dir / filename
        if link.exists():
            link.unlink()
        link.symlink_to(src)

        for s in protocol.get("steps", []):
            if s["name"] == step_choice:
                s.setdefault("files", []).append(filename)
                step_counts[step_choice] = step_counts.get(step_choice, 0) + 1
                break

    # Sweep metadata: auto-detect for IV files
    iv_techniques = {"iv", "iv-sweep", "iv-breakdown", "iv-leakage"}
    from science_cli.core.sweep_metadata import extract_sweep_from_file, update_protocol_with_sweep
    def _norm_fnames(files):
        out = []
        for e in files:
            if isinstance(e, str): out.append(e)
            elif isinstance(e, dict) and "file" in e: out.append(e["file"])
        return out
    for fname in selected:
        step_name = technique = ""
        for s in protocol.get("steps", []):
            if fname in _norm_fnames(s.get("files", [])):
                step_name = s["name"]
                technique = s.get("technique", "")
                break
        if step_name and technique.lower() in iv_techniques:
            src = raw_dir / fname
            if src.exists():
                segs = extract_sweep_from_file(str(src))
                if segs:
                    update_protocol_with_sweep(yaml_path, step_name, fname, segs)
                    ndirs = ", ".join(sg["direction"] for sg in segs)
                    rprint(f"  [dim]  \u21b3 sweep: {len(segs)} seg [{ndirs}] @ {segs[0]['sweep_rate_v_s']} V/s[/dim]")

    with open(yaml_path, "w") as f:
        yaml.dump(protocol, f, default_flow_style=False, sort_keys=False)

    rprint(f"[bold green]\u2713[/bold green] Files assigned to protocol '{proto_name}'")
    for fname in selected:
        rprint(f"  [dim]\u2022 {fname}[/dim]")

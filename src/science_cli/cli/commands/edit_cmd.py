"""edit command handler — edit protocol/metadata/data."""

import shutil

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


def edit_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("edit")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "-m":
        if not sub_args:
            console.print("[yellow]Usage: edit -m protocol|metadata [flags][/yellow]")
            return
        mode = sub_args[0]
        mode_args = sub_args[1:]

        if mode == "protocol":
            _edit_protocol(mode_args)
        elif mode == "metadata":
            _edit_metadata(mode_args)
        elif mode == "data":
            _edit_data(mode_args)
        else:
            console.print(f"[yellow]Unknown edit mode: {mode}[/yellow]")
    else:
        console.print(f"[yellow]Unknown edit subcommand: {sub}[/yellow]")


def _edit_protocol(args: list) -> None:
    _, flags = _parse_flags(args)

    name = flags.get("n") or flags.get("name")
    if not name:
        console.print("[yellow]Required: -n / --name (protocol name)[/yellow]")
        return

    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    from science_cli.core.paths import sanitize_protocol_name
    safe_name = sanitize_protocol_name(name)
    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(safe_name)
    if not yaml_path.exists():
        console.print(f"[red]Protocol '{safe_name}' not found.[/red]")
        return

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    new_name = flags.get("new-name") or flags.get("nn")
    new_desc = flags.get("desc") or flags.get("description")
    steps_raw = flags.get("step")
    techs_raw = flags.get("t") or flags.get("technique")
    devs_raw = flags.get("d") or flags.get("device")

    if new_name:
        safe_new = sanitize_protocol_name(new_name)
        data["name"] = safe_new
        old_pdir = paths.protocol_dir / safe_name
        new_pdir = paths.protocol_dir / safe_new
        if new_pdir.exists() and new_pdir != old_pdir:
            # Allow rename if existing target is an empty directory leftover
            # from a previous incomplete rename.
            empties = list(new_pdir.iterdir()) if new_pdir.is_dir() else [None]
            if not empties:
                new_pdir.rmdir()
            else:
                console.print(f"[red]Protocol '{safe_new}' already exists.[/red]")
                return

        new_yaml = new_pdir / f"{safe_new}.yaml"
        flat_yaml = paths.protocol_dir / f"{safe_name}.yaml"

        if old_pdir.is_dir():
            old_pdir.rename(new_pdir)
            old_yaml = new_pdir / f"{safe_name}.yaml"
        elif flat_yaml.exists():
            new_pdir.mkdir(parents=True, exist_ok=True)
            old_yaml = flat_yaml
        else:
            console.print(f"[red]Protocol '{safe_name}' not found on disk.[/red]")
            return

        if old_yaml != new_yaml and old_yaml.exists():
            old_yaml.rename(new_yaml)

        yaml_path = new_yaml
        safe_name = safe_new  # update for subsequent step operations

    if new_desc:
        data["description"] = new_desc

    # --rm-step <name>: remove ALL steps matching name from the YAML (handles duplicates)
    rm_step = flags.get("rm-step")
    if rm_step:
        steps = data.get("steps", [])
        removed = []
        new_steps = []
        for s in steps:
            if s["name"] == rm_step:
                removed.append(s)
            else:
                new_steps.append(s)
        if not removed:
            console.print(f"[yellow]Step '{rm_step}' not found in protocol.[/yellow]")
        else:
            data["steps"] = new_steps
            rprint(f"[bold green]✓[/bold green] Removed {len(removed)} step(s): '{rm_step}'")
            step_dir = paths.step_dir(safe_name, rm_step)
            import questionary
            if step_dir.exists():
                if questionary.confirm(
                    f"Delete step directory '{rm_step}' and all its contents from disk?",
                    default=False
                ).ask():
                    shutil.rmtree(step_dir)
                    rprint(f"[bold yellow]🗑[/bold yellow] Step directory '{rm_step}' deleted")
                else:
                    rprint(f"[dim]Step directory '{rm_step}' kept on disk[/dim]")
            else:
                rprint(f"[dim]No directory found for step '{rm_step}'[/dim]")

    # --reorder <s1,s2,...>: reorder steps in the YAML
    reorder_raw = flags.get("reorder")
    if reorder_raw:
        desired_order = [s.strip() for s in reorder_raw.split(",") if s.strip()]
        current_steps = data.get("steps", [])
        current_names = {s["name"] for s in current_steps}
        desired_set = set(desired_order)
        missing = desired_set - current_names
        extra = current_names - desired_set
        if missing:
            console.print(f"[red]Step(s) not found: {', '.join(missing)}[/red]")
            return
        if extra:
            console.print(
                f"[yellow]Warning: {len(extra)} step(s) not in reorder list "
                f"will be appended: {', '.join(sorted(extra))}[/yellow]"
            )
        step_map = {s["name"]: s for s in current_steps}
        reordered = [step_map[n] for n in desired_order]
        for extra_name in sorted(extra):
            reordered.append(step_map[extra_name])
        data["steps"] = reordered
        rprint(f"[bold green]✓[/bold green] Steps reordered: {', '.join(desired_order)}")

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
            data.setdefault("steps", []).append(entry)
            step_dir = paths.step_dir(safe_name, sn)
            step_dir.mkdir(parents=True, exist_ok=True)
            (step_dir / "results").mkdir(parents=True, exist_ok=True)

    if techs_raw and not steps_raw:
        techs = [t.strip() for t in techs_raw.split(",") if t.strip()]
        for i, s in enumerate(data.get("steps", [])):
            if i < len(techs):
                s["technique"] = techs[i]

    if devs_raw and not steps_raw:
        devs = [d.strip() for d in devs_raw.split(",") if d.strip()]
        for i, s in enumerate(data.get("steps", [])):
            if i < len(devs):
                s["device"] = devs[i]

    if new_name:
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        rprint(f"[bold green]✓[/bold green] Protocol renamed to '{safe_new}'")
    else:
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        rprint(f"[bold green]✓[/bold green] Protocol '{safe_name}' updated")


def _edit_metadata(args: list) -> None:
    _, flags = _parse_flags(args)

    name = flags.get("n") or flags.get("name")
    step = flags.get("step")
    techs_raw = flags.get("t") or flags.get("technique")
    devs_raw = flags.get("d") or flags.get("device")
    files_raw = flags.get("files")

    if not name:
        from science_cli.core.session import load_session
        name = load_session().get("last_protocol", "")
    if not name:
        console.print("[yellow]Required: -n / --name (protocol name), or open a protocol first[/yellow]")
        return

    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    from science_cli.core.paths import sanitize_protocol_name
    safe_name = sanitize_protocol_name(name)
    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(safe_name)
    if not yaml_path.exists():
        console.print(f"[red]Protocol '{safe_name}' not found.[/red]")
        return

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    step_names = [s.strip() for s in step.split(",") if s.strip()] if step else [s["name"] for s in data.get("steps", [])]

    if techs_raw:
        techs = [t.strip() for t in techs_raw.split(",") if t.strip()]
        for i, sn in enumerate(step_names):
            for s in data.get("steps", []):
                if s["name"] == sn:
                    if i < len(techs):
                        s["technique"] = techs[i]

    if devs_raw:
        devs = [d.strip() for d in devs_raw.split(",") if d.strip()]
        for i, sn in enumerate(step_names):
            for s in data.get("steps", []):
                if s["name"] == sn:
                    if i < len(devs):
                        s["device"] = devs[i]

    if files_raw:
        files = [f.strip() for f in files_raw.split(",") if f.strip()]
        for sn in step_names:
            for s in data.get("steps", []):
                if s["name"] == sn:
                    s["files"] = files

    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    rprint(f"[bold green]✓[/bold green] Metadata updated for '{safe_name}'")
    if step:
        rprint(f"  [dim]Steps: {', '.join(step_names)}[/dim]")


def _edit_data(args: list) -> None:
    """Move/reassign files between protocol steps."""
    import questionary

    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    # Resolve protocol: session first, then fzf picker
    from science_cli.core.session import load_session
    sess = load_session()
    proto_name = sess.get("last_protocol", "")

    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    if not proto_yamls:
        console.print("[yellow]No protocol YAMLs found.[/yellow]")
        return

    if proto_name:
        yaml_path = paths.protocol_yaml(proto_name)
        if not yaml_path.exists():
            proto_name = ""

    if not proto_name:
        from science_cli.core.fzf_utils import fzf_select
        proto_names = [p.stem for p in proto_yamls]
        choice = fzf_select(proto_names, prompt="Select protocol:", multi=False)
        if not choice:
            console.print("[yellow]No protocol selected.[/yellow]")
            return
        proto_name = choice[0]

    yaml_path = paths.protocol_yaml(proto_name)
    with open(yaml_path) as f:
        protocol = yaml.safe_load(f) or {}

    steps = protocol.get("steps", [])
    if not steps:
        console.print("[yellow]No steps in protocol.[/yellow]")
        return

    # Collect all files across all steps: (step_name, filename)
    all_files: list[tuple[str, str]] = []
    for s in steps:
        for entry in s.get("files", []):
            fname = entry["file"] if isinstance(entry, dict) else entry
            all_files.append((s["name"], fname))

    if not all_files:
        console.print("[yellow]No files assigned in protocol.[/yellow]")
        return

    # fzf multi-select: column format via build_fzf_display
    from science_cli.core.fzf_utils import build_fzf_display, fzf_select
    display_items = [build_fzf_display(proto_name, sn, fn, show_protocol=False) for sn, fn in all_files]
    selected_displays = fzf_select(
        display_items,
        prompt=f"{proto_name} | Select files to move (Tab to multi-select):",
        multi=True,
    )
    if not selected_displays:
        console.print("[yellow]No files selected.[/yellow]")
        return

    # Map selected displays back to (step_name, filename)
    # Build a lookup: display key -> (step_name, filename)
    # Handle duplicate filenames across steps by using index
    display_to_file: dict[str, tuple[str, str]] = {}
    for i, (sn, fn) in enumerate(all_files):
        key = build_fzf_display(proto_name, sn, fn, show_protocol=False)
        if key in display_to_file:
            key = build_fzf_display(proto_name, sn, fn, show_protocol=False) + f"  [{i}]"
            display_to_file[key] = (sn, fn)
        else:
            display_to_file[key] = (sn, fn)

    selected_files: list[tuple[str, str]] = []
    for sel in selected_displays:
        if sel in display_to_file:
            selected_files.append(display_to_file[sel])

    if not selected_files:
        console.print("[yellow]No valid files selected.[/yellow]")
        return

    # Build step choices showing existing file counts
    step_choices = []
    for s in steps:
        sn = s.get("name", "?")
        t = s.get("technique", "")
        n_files = len(s.get("files", []))
        label = sn
        if t:
            label += f" ({t})"
        label += f" — {n_files} files"
        step_choices.append(questionary.Choice(title=label, value=sn))
    step_choices.append(questionary.Choice(title="Skip", value="__skip__"))

    target_step = questionary.select(
        f"Reassign {len(selected_files)} file(s) to which step?",
        choices=step_choices,
    ).ask()
    if not target_step or target_step == "__skip__":
        console.print("[yellow]Cancelled.[/yellow]")
        return

    # Resolve raw data dir for symlink source
    raw_dir = proj / "data" / "raw"

    # Track moves for summary
    moves: list[dict] = []

    # Step 1: Remove files from old steps in the YAML
    # Group selected files by their source step
    from collections import defaultdict
    files_by_source: dict[str, list[str]] = defaultdict(list)
    for old_step_name, fname in selected_files:
        files_by_source[old_step_name].append(fname)

    for s in steps:
        step_files = s.get("files", [])
        to_remove_names = [fn for old_sn, fn in selected_files if old_sn == s["name"]]
        if to_remove_names:
            kept = []
            for entry in step_files:
                entry_name = entry["file"] if isinstance(entry, dict) else entry
                if entry_name not in to_remove_names:
                    kept.append(entry)
            if not kept:
                s.pop("files", None)
            else:
                s["files"] = kept

    # Step 2: Ensure target step has a files list and add selected files
    target_step_data = None
    for s in steps:
        if s["name"] == target_step:
            target_step_data = s
            existing_fnames = set()
            for entry in s.get("files", []):
                existing_fnames.add(entry["file"] if isinstance(entry, dict) else entry)
            new_fnames = [fn for _, fn in selected_files if fn not in existing_fnames]
            s.setdefault("files", []).extend(new_fnames)
            break

    if target_step_data is None:
        console.print(f"[red]Target step '{target_step}' not found.[/red]")
        return

    # Step 3: Update symlinks on disk
    target_step_dir = paths.step_dir(proto_name, target_step)
    target_step_dir.mkdir(parents=True, exist_ok=True)
    (target_step_dir / "results").mkdir(parents=True, exist_ok=True)

    for old_step_name, fname in selected_files:
        # Remove old symlink (only if it's a symlink, not a real file)
        old_link = paths.step_dir(proto_name, old_step_name) / fname
        if old_link.is_symlink():
            old_link.unlink()
        elif old_link.exists():
            console.print(f"[yellow]Warning: '{fname}' in '{old_step_name}' is not a symlink, skipping removal[/yellow]")

        # Create new symlink in target step
        src = raw_dir / fname
        new_link = target_step_dir / fname
        if new_link.exists():
            new_link.unlink()
        if src.exists():
            new_link.symlink_to(src)

        moves.append({"file": fname, "from": old_step_name, "to": target_step})

    # Step 4: Save YAML
    with open(yaml_path, "w") as f:
        yaml.dump(protocol, f, default_flow_style=False, sort_keys=False)

    # Step 5: Print summary
    rprint(f"\n[bold green]✓[/bold green] Moved {len(moves)} file(s) to step '[bold white]{target_step}[/bold white]'")
    for m in moves:
        rprint(f"  [dim]• {m['file']}: {m['from']} → {m['to']}[/dim]")

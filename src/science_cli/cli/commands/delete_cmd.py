"""delete command handler — remove protocol/metadata/data files."""

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


def delete_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("delete")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "-m":
        if not sub_args:
            console.print("[yellow]Usage: delete -m protocol|metadata [flags][/yellow]")
            return
        mode = sub_args[0]
        mode_args = sub_args[1:]

        if mode == "protocol":
            _delete_protocol(mode_args)
        elif mode == "metadata":
            _delete_metadata(mode_args)
        elif mode == "data":
            _delete_data(mode_args)
        else:
            console.print(f"[yellow]Unknown delete mode: {mode}[/yellow]")
    else:
        console.print(f"[yellow]Unknown delete subcommand: {sub}[/yellow]")


def _delete_protocol(args: list) -> None:
    _, flags = _parse_flags(args)

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

    from science_cli.core.paths import sanitize_protocol_name
    safe_name = sanitize_protocol_name(name)
    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(safe_name)
    if not yaml_path.exists():
        console.print(f"[red]Protocol '{safe_name}' not found.[/red]")
        return

    import questionary
    if not questionary.confirm(f"Delete protocol '{safe_name}' and all step folders?", default=False).ask():
        console.print("[yellow]Cancelled.[/yellow]")
        return

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    for s in data.get("steps", []):
        step_dir = paths.step_dir(safe_name, s["name"])
        if step_dir.exists():
            import shutil
            shutil.rmtree(step_dir)

    # Remove the protocol directory itself if empty after removing steps
    proto_subdir = paths.protocol_subdir(safe_name)
    if proto_subdir.exists():
        try:
            proto_subdir.rmdir()  # only removes if empty
        except OSError:
            pass  # directory still has files (e.g. not all steps were listed in YAML)

    yaml_path.unlink()

    from science_cli.core.session import load_session, save_session
    session = load_session()
    if session.get("last_protocol") == safe_name:
        save_session({"last_protocol": None})

    rprint(f"[bold green]✓[/bold green] Deleted protocol '{safe_name}'")


def _delete_metadata(args: list) -> None:
    _, flags = _parse_flags(args)

    name = flags.get("n") or flags.get("name")
    step = flags.get("step")
    clear_all = flags.get("all", False)

    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    if not name and not clear_all:
        console.print("[yellow]Required: -n / --name (protocol name) or --all[/yellow]")
        return

    if clear_all:
        import questionary
        if not questionary.confirm("Clear metadata from all protocol YAMLs?", default=False).ask():
            return
        paths = ProjectPaths(proj)
        for yf in paths.list_protocol_yamls():
            with open(yf) as f:
                data = yaml.safe_load(f) or {}
            for s in data.get("steps", []):
                s.pop("files", None)
            with open(yf, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        rprint("[bold green]✓[/bold green] Cleared all file assignments")
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

    if step:
        step_names = [s.strip() for s in step.split(",") if s.strip()]
        for s in data.get("steps", []):
            if s["name"] in step_names:
                s.pop("files", None)
        rprint(f"[bold green]✓[/bold green] Removed files from steps: {', '.join(step_names)}")
    else:
        for s in data.get("steps", []):
            s.pop("files", None)
        rprint(f"[bold green]✓[/bold green] Removed all file assignments from '{safe_name}'")

    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _delete_data(args: list) -> None:
    """Delete data files from protocol YAML file lists.

    Flags:
        --fzf         Interactive fzf multi-select picker
        --step <name> Limit to a specific step directory
    """
    _, flags = _parse_flags(args)

    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    from science_cli.core.session import load_session
    session = load_session()
    proto_name = session.get("last_protocol", "")
    if not proto_name:
        console.print("[yellow]No protocol selected. Open one first.[/yellow]")
        return

    from science_cli.core.paths import sanitize_protocol_name
    safe_name = sanitize_protocol_name(proto_name)
    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(safe_name)
    if not yaml_path.exists():
        console.print(f"[red]Protocol YAML not found: {yaml_path}[/red]")
        return

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    step_filter = flags.get("step", "")
    steps = data.get("steps", [])

    # Collect all files from all (or filtered) steps
    all_entries: list[tuple[str, str, int | str]] = []  # (step_name, filename, entry_idx)
    for si, s in enumerate(steps):
        step_name = s.get("name", "")
        if step_filter and step_name != step_filter:
            continue
        for fi, entry in enumerate(s.get("files", [])):
            fname = entry["file"] if isinstance(entry, dict) else entry
            all_entries.append((step_name, fname, fi))

    if not all_entries:
        if step_filter:
            console.print(f"[yellow]No files found in step '{step_filter}'.[/yellow]")
        else:
            console.print("[yellow]No files found in protocol YAML.[/yellow]")
        return

    to_remove: list[tuple[int, int]] = []  # (step_idx, file_idx)

    if flags.get("fzf"):
        from science_cli.core.fzf_utils import fzf_select
        items = [f"{step_name}/{fname}" for step_name, fname, _ in all_entries]
        selected = fzf_select(
            items=items,
            prompt="Select files to remove >",
            multi=True,
            preview="head -3 {}",
            preview_window="right:50%:border-sharp",
        )
        if not selected:
            console.print("[yellow]No files selected.[/yellow]")
            return
        selected_set = set(selected)
        for step_name, fname, fi in all_entries:
            key = f"{step_name}/{fname}"
            if key in selected_set:
                si = next(i for i, s in enumerate(steps) if s.get("name") == step_name)
                to_remove.append((si, fi))
        for si, fi in reversed(to_remove):
            files_list = steps[si].get("files", [])
            if fi < len(files_list):
                entry = files_list[fi]
                removed_name = entry["file"] if isinstance(entry, dict) else entry
                del files_list[fi]
                console.print(f"  Removed: [dim]{step_name}/{removed_name}[/dim]")
    else:
        console.print("[yellow]Use --fzf to interactively select files.[/yellow]")
        return

    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    rprint(f"[bold green]✓[/bold green] Removed {len(to_remove)} file(s) from '{safe_name}' YAML")
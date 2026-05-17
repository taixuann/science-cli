"""delete command handler — remove protocol/metadata."""

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
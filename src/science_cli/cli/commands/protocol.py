"""protocol command handler."""

from rich.console import Console

from science_cli.cli.help import show_command_help

console = Console()


def protocol_handler(args: list) -> None:
    """Handle `protocol` command and subcommands."""
    from science_cli.core.project import get_current_project_path

    if not args or args[0] in ("--help", "-h"):
        show_command_help("protocol")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "list":
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(proj)
        yamls = paths.list_protocol_yamls()
        if not yamls:
            console.print("[yellow]No protocols found.[/yellow]")
            return
        console.print("[bold]Available protocols:[/bold]")
        for p in yamls:
            console.print(f"  • {p.stem}")

    elif sub == "run":
        if not sub_args:
            console.print("[yellow]Usage: protocol run <name>[/yellow]")
            return
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(proj)
        proto_yaml = paths.protocol_yaml(sub_args[0])
        if not proto_yaml.exists():
            console.print(f"[red]Protocol '{sub_args[0]}' not found.[/red]")
            return
        console.print(f"[dim]Running protocol '{sub_args[0]}' — open YAML to configure steps.[/dim]")

    elif sub == "create":
        import questionary
        import yaml

        from science_cli.core.paths import ProjectPaths
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open. Select a project first.[/yellow]")
            return
        name = questionary.text("Protocol name:").ask()
        if not name:
            return
        desc = questionary.text("Description (optional):").ask() or ""
        steps_raw = questionary.text("Steps (comma-separated, e.g. 1_deposition,2_char):").ask()
        if not steps_raw:
            console.print("[yellow]At least one step required.[/yellow]")
            return
        step_names = [s.strip() for s in steps_raw.split(",") if s.strip()]
        protocol_data = {
            "name": name,
            "description": desc,
            "steps": [{"name": sn, "technique": ""} for sn in step_names],
        }
        paths = ProjectPaths(proj)
        paths.protocol_dir.mkdir(parents=True, exist_ok=True)
        protocol_file = paths.protocol_yaml_new(name)
        protocol_file.parent.mkdir(parents=True, exist_ok=True)
        if protocol_file.exists():
            proceed = questionary.confirm("Overwrite existing?", default=False).ask()
            if not proceed:
                return
        for sn in step_names:
            (paths.protocol_subdir(name) / sn / "results").mkdir(parents=True, exist_ok=True)
        with open(protocol_file, "w") as f:
            yaml.dump(protocol_data, f, default_flow_style=False, sort_keys=False)
        console.print(f"[bold green]Protocol created: {protocol_file}[/bold green]")

    elif sub == "edit":
        if not sub_args:
            console.print("[yellow]Usage: protocol edit <name>[/yellow]")
            return
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(proj)
        proto_yaml = paths.protocol_yaml(sub_args[0])
        if not proto_yaml.exists():
            console.print(f"[red]Protocol '{sub_args[0]}' not found.[/red]")
            return
        import subprocess
        try:
            subprocess.run(["code", str(proto_yaml)], check=False)
        except FileNotFoundError:
            console.print("[red]VSCode not found. Set EDITOR env var.[/red]")

    elif sub == "resume":
        if not sub_args:
            console.print("[yellow]Usage: protocol resume <name>[/yellow]")
            return
        console.print(f"[dim]Resume not yet implemented for '{sub_args[0]}'.[/dim]")

    elif sub == "overlap":
        if not sub_args:
            console.print("[yellow]Usage: protocol overlap <name>[/yellow]")
            return
        console.print(f"[dim]Overlap view not yet implemented for '{sub_args[0]}'.[/dim]")

    else:
        console.print(f"[yellow]Unknown protocol subcommand: {sub}[/yellow]")
        show_command_help("protocol")

"""project command handler."""

from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help

console = Console()


def project_handler(args: list) -> None:
    """Handle `project` command and subcommands."""
    from science_cli.core.project import list_projects, open_project, get_current_project_path

    if not args or args[0] in ("--help", "-h"):
        show_command_help("project")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "list":
        projects = list_projects()
        if projects:
            console.print("[bold]Projects:[/bold]")
            for p in projects:
                console.print(f"  {p}")
        else:
            console.print("[yellow]No projects found.[/yellow]")

    elif sub == "open":
        if not sub_args:
            console.print("[yellow]Usage: project open <name>[/yellow]")
            return
        open_project(sub_args[0])
        from science_cli.core.session import set_last_project
        set_last_project(sub_args[0])

    elif sub == "create":
        from science_cli.core.project import open_project
        from science_cli.core.session import set_last_project
        import questionary
        name = questionary.text("New project name:").ask()
        if not name:
            return
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip().lower().replace(" ", "_")
        if not safe_name:
            console.print("[red]Invalid project name.[/red]")
            return
        from science_cli.core.project import _get_projects_root
        projects_root = _get_projects_root()
        project_path = projects_root / safe_name
        if project_path.exists():
            console.print(f"[yellow]Project '{safe_name}' already exists.[/yellow]")
            return
        dirs = [
            project_path / "data" / "raw",
            project_path / "protocol",
            project_path / "results",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        console.print(f"[bold green]Created project: {safe_name}[/bold green]")
        open_project(safe_name)
        set_last_project(safe_name)

    elif sub in ("status", "stats"):
        from science_cli.core.project import project_status
        info = project_status()
        if "error" in info:
            console.print(f"[yellow]{info['error']}[/yellow]")
        else:
            console.print(f"[bold]Project:[/bold] {info['name']}")
            console.print(f"  Path: {info['path']}")
            console.print(f"  Raw files: {info['raw_files']}")
            console.print(f"  Protocols: {info['protocols']}")
        if sub == "stats":
            proj = get_current_project_path()
            if proj:
                from science_cli.core.technique import detect_technique
                from pathlib import Path
                raw_dir = proj / "data" / "raw"
                if raw_dir.exists():
                    ec_tags = {"CV": 0, "CA": 0, "EIS": 0}
                    for f in raw_dir.iterdir():
                        if f.is_file():
                            t = detect_technique(f.name)
                            if t in ec_tags:
                                ec_tags[t] += 1
                    console.print(f"\n[bold]Files by technique:[/bold]")
                    for t, n in ec_tags.items():
                        console.print(f"  {t}: {n}")
    
    elif sub == "migrate":
        _project_migrate()

    else:
        console.print(f"[yellow]Unknown project subcommand: {sub}[/yellow]")
        show_command_help("project")


def _project_migrate() -> None:
    """Migrate flat protocol YAMLs + step directories to nested layout.

    Phase 1: YAML migration: protocol/<name>.yaml → protocol/<name>/<name>.yaml
    Phase 2: Step migration:  protocol/<step>/ → protocol/<proto>/<step>/
    """
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open. Use 'project open <name>' first.[/yellow]")
        return

    proto_dir = proj / "protocol"
    if not proto_dir.exists():
        console.print("[yellow]No protocol/ directory found.[/yellow]")
        return

    from science_cli.core.paths import ProjectPaths
    import yaml
    import shutil

    paths = ProjectPaths(proj)

    # ── Phase 1: Migrate YAML files ──────────────────────────
    rprint("[bold]Phase 1: Migrating protocol YAML files...[/bold]")
    yaml_result = paths.migrate_protocol_yamls()
    if yaml_result["migrated"] > 0:
        rprint(f"  [green]Migrated:[/green] {yaml_result['migrated']} YAML file(s)")
    if yaml_result["skipped"] > 0:
        rprint(f"  [dim]Skipped (already nested):[/dim] {yaml_result['skipped']}")
    if yaml_result["errors"]:
        for err in yaml_result["errors"]:
            rprint(f"  [red]Error:[/red] {err}")

    # ── Phase 2: Migrate step directories ────────────────────
    yaml_files = paths.list_protocol_yamls()
    if not yaml_files:
        rprint("[yellow]No protocol YAMLs found for step migration.[/yellow]")
        return

    rprint("[bold]Phase 2: Migrating step directories...[/bold]")
    moved = 0
    skipped = 0
    warnings: list[str] = []

    for yf in yaml_files:
        safe_name = yf.stem
        with open(yf) as f:
            data = yaml.safe_load(f) or {}

        steps = data.get("steps", [])
        if not steps:
            continue

        proto_subdir = proto_dir / safe_name

        for s in steps:
            sn = s["name"]
            old_path = proto_dir / sn
            new_path = proto_subdir / sn

            if not old_path.exists():
                if not new_path.exists():
                    warnings.append(
                        f"  [yellow]Step '{sn}' in protocol '{safe_name}': "
                        f"no directory found at old or new location[/yellow]"
                    )
                else:
                    skipped += 1
                continue

            if new_path.exists():
                if not old_path.samefile(new_path):
                    warnings.append(
                        f"  [yellow]Step '{sn}' in protocol '{safe_name}': "
                        f"both old and new directories exist — skipped[/yellow]"
                    )
                    skipped += 1
                else:
                    skipped += 1
                continue

            if old_path == proto_subdir:
                tmp_path = proto_dir / f"{safe_name}.tmp_migrate"
                old_path.rename(tmp_path)
                proto_subdir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(tmp_path), str(new_path))
            else:
                proto_subdir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))

            rprint(f"  [green]Moved:[/green] {old_path.relative_to(proj)} \u2192 {new_path.relative_to(proj)}")
            moved += 1

    if moved > 0:
        rprint(f"\n[bold green]\u2713[/bold green] Migrated {moved} step director{'y' if moved == 1 else 'ies'}")
    if skipped > 0:
        rprint(f"[dim]  Skipped: {skipped}[/dim]")
    if warnings:
        for w in warnings:
            rprint(w)
    if moved == 0 and skipped == 0:
        rprint("[dim]No step directories to migrate — all already in new layout.[/dim]")

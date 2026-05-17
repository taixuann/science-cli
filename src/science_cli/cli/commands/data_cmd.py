"""data command handler — import, export, assign."""

from pathlib import Path
from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help

console = Console()


def data_handler(args: list) -> None:
    """Handle `data` command and subcommands."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("data")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "import":
        if not sub_args:
            console.print("[yellow]Usage: data import <source_dir>[/yellow]")
            return
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        source = Path(sub_args[0]).expanduser()
        if not source.exists():
            console.print(f"[red]Directory not found: {source}[/red]")
            return
        raw_dir = proj / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        copied = 0
        for f in sorted(source.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                dest = raw_dir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    copied += 1
        console.print(f"[green]✓[/green] Imported {copied} file(s) to {raw_dir}")

    elif sub == "export":
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        results_dir = proj / "results"
        if not results_dir.exists():
            console.print("[yellow]No results to export.[/yellow]")
            return
        export_dir = Path(sub_args[0]).expanduser() if sub_args else Path.home() / "Desktop" / f"{proj.name}_results"
        export_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        for item in results_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(results_dir)
                dest = export_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
        console.print(f"[green]✓[/green] Exported to {export_dir}")

    elif sub == "assign":
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if proj:
            # Placeholder: batch assignment wizard not yet implemented
            console.print("[yellow]Batch assign wizard not yet implemented.[/yellow]")
        else:
            console.print("[yellow]No project open.[/yellow]")

    else:
        console.print(f"[yellow]Unknown data subcommand: {sub}[/yellow]")
        show_command_help("data")

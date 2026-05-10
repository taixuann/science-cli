"""metadata command handler — show, edit, undo."""

from pathlib import Path
from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help

console = Console()


def metadata_handler(args: list) -> None:
    """Handle `metadata` command and subcommands."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("metadata")
        return

    sub = args[0]
    sub_args = args[1:]

    from science_cli.core.project import get_current_project_path
    from science_cli.core.legacy import lookup_metadata

    if sub == "show":
        if not sub_args:
            console.print("[yellow]Usage: metadata show <file>[/yellow]")
            return
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        meta = lookup_metadata(proj, sub_args[0])
        if meta:
            for k, v in meta.items():
                console.print(f"  {k}: [bold]{v}[/bold]")
        else:
            console.print(f"[yellow]No metadata found for '{sub_args[0]}'.[/yellow]")

    elif sub == "edit":
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        meta_file = proj / "data" / "metadata.yaml"
        if not meta_file.exists():
            console.print("[yellow]No metadata.yaml found.[/yellow]")
            return
        import subprocess
        try:
            subprocess.run(["code", str(meta_file)], check=False)
        except FileNotFoundError:
            console.print("[red]VSCode not found.[/red]")

    elif sub == "undo":
        from science_cli.core.legacy import undo_metadata
        proj = get_current_project_path()
        if not proj:
            console.print("[yellow]No project open.[/yellow]")
            return
        undo_metadata(proj)

    else:
        console.print(f"[yellow]Unknown metadata subcommand: {sub}[/yellow]")
        show_command_help("metadata")

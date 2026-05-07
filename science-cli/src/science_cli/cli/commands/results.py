"""results command — list saved figures/analysis by protocol and step."""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from science_cli.cli.help import show_command_help

console = Console()


def results_handler(args: list) -> None:
    if args and args[0] in ("--help", "-h"):
        show_command_help("results")
        return

    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open. Use 'project open <name>' first.[/yellow]")
        return

    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    if not proto_yamls:
        console.print("[yellow]No protocols found.[/yellow]")
        return

    rprint(f"\n[bold]Results for project:[/bold] {proj.name}\n")

    for py in proto_yamls:
        pname = py.stem
        proto_path = paths.protocol_subdir(pname)
        total = 0

        rprint(f"  [bold cyan]{pname}[/bold cyan]")

        # Step-level results
        if proto_path.exists():
            step_dirs = sorted(proto_path.iterdir())
            for sd in step_dirs:
                if not sd.is_dir():
                    continue
                results_dir = sd / "results"
                if results_dir.exists():
                    files = sorted(results_dir.iterdir())
                    pdfs = [f for f in files if f.suffix in (".pdf", ".svg", ".png")]
                    if pdfs:
                        for pf in pdfs:
                            size = pf.stat().st_size
                            rprint(f"    [dim]•[/dim] {sd.name}/{pf.name}  [dim]({_fmt_size(size)})[/dim]")
                            total += 1

        # Project-level results
        proj_results = proj / "results"
        if proj_results.exists():
            proto_files = sorted(proj_results.glob(f"{pname}_*.pdf")) + \
                          sorted(proj_results.glob(f"*{pname}*.pdf")) + \
                          sorted(proj_results.glob(f"{pname}_*.png"))
            if proto_files:
                for pf in proto_files:
                    size = pf.stat().st_size
                    rprint(f"    [dim]•[/dim] {pf.name}  [dim]({_fmt_size(size)})[/dim]")
                    total += 1

        if total == 0:
            rprint(f"    [dim]No results yet.[/dim]")
        rprint("")

    # Also show standalone results
    proj_results = proj / "results"
    if proj_results.exists():
        orphaned = sorted(proj_results.glob("*"))
        orphaned = [f for f in orphaned if f.is_file() and f.suffix in (".pdf", ".svg", ".png")]
        direct_results = [f for f in orphaned if not any(f.name.startswith(py.stem) for py in proto_yamls)]
        if direct_results:
            rprint(f"  [bold]Other results:[/bold]")
            for f in direct_results:
                size = f.stat().st_size
                rprint(f"    [dim]•[/dim] {f.name}  [dim]({_fmt_size(size)})[/dim]")


def _fmt_size(bytes: int) -> str:
    if bytes < 1024:
        return f"{bytes}B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.0f}KB"
    else:
        return f"{bytes / 1024 ** 2:.1f}MB"

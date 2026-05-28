"""results command — list saved figures/analysis by protocol and step."""

import subprocess
from collections import defaultdict
from pathlib import Path

from rich.console import Console

from science_cli.cli.help import show_command_help

console = Console()


def results_handler(args: list) -> None:
    if args and args[0] in ("--help", "-h"):
        show_command_help("results")
        return

    use_fzf = True  # fzf is now default

    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open. Use 'project open <name>' first.[/yellow]")
        return

    paths = ProjectPaths(proj)
    proto_yamls = paths.list_protocol_yamls()
    if not proto_yamls:
        console.print("[yellow]No protocols found.[/yellow]")
        return

    # ── Collect all result files as structured tuples ──
    # Each entry: (protocol_name, step_dir_name, file_path)
    result_files: list[tuple[str, str, Path]] = []

    for py in proto_yamls:
        pname = py.stem
        proto_path = paths.protocol_subdir(pname)

        # Step-level results
        if proto_path.exists():
            for sd in sorted(proto_path.iterdir()):
                if not sd.is_dir():
                    continue
                results_dir = sd / "results"
                if results_dir.exists():
                    for pf in sorted(results_dir.iterdir()):
                        if pf.suffix in (".pdf", ".svg", ".png"):
                            result_files.append((pname, sd.name, pf))

    # ── F8: FZF mode — pipe results through fzf for interactive opening ──
    if use_fzf:
        if not result_files:
            console.print("[yellow]No result files found.[/yellow]")
            return
        from science_cli.core.fzf_utils import build_fzf_display, fzf_select
        display_lines = [build_fzf_display(pname, sd_name, pf.name, width_proto=22, width_step=18) for pname, sd_name, pf in result_files]
        selected = fzf_select(display_lines, prompt="Select result to open:", multi=False)
        if selected:
            for pname, sd_name, pf in result_files:
                if build_fzf_display(pname, sd_name, pf.name, width_proto=22, width_step=18) == selected[0]:
                    subprocess.run(["open", str(pf)], check=False)
                    console.print(f"[dim]Opened: {pf.name}[/dim]")
                    break
        return

    # ── F9: Grouped Rich display ──
    if not result_files:
        # Check for project-level / orphaned results
        proj_results = proj / "results"
        has_orphaned = False
        if proj_results.exists():
            orphaned = sorted(proj_results.glob("*"))
            orphaned = [f for f in orphaned if f.is_file() and f.suffix in (".pdf", ".svg", ".png")]
            if orphaned:
                has_orphaned = True
                console.print("\n[bold]Other results:[/bold]")
                for f in orphaned:
                    size = f.stat().st_size
                    console.print(f"  [dim]• {f.name}  ({_fmt_size(size)})[/dim]")
                console.print()

        if not has_orphaned:
            console.print("[dim]No results yet.[/dim]\n")
        return

    console.print(f"\n[bold]Results for project:[/bold] {proj.name}\n")

    # Group by protocol, then by step
    by_protocol: dict[str, dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))
    for pname, sd_name, pf in result_files:
        by_protocol[pname][sd_name].append(pf)

    for pname in sorted(by_protocol.keys()):
        console.print(f"  [bold cyan]📁 protocol/{pname}[/bold cyan]")

        steps = by_protocol[pname]
        total_proto = 0
        for sd_name in sorted(steps.keys()):
            files = steps[sd_name]
            total_proto += len(files)
            console.print(f"    [bold yellow]┌─ {sd_name} ──[/bold yellow]")
            for pf in sorted(files):
                size = pf.stat().st_size
                console.print(f"      [dim]{pf.name:<40s} {_fmt_size(size)}[/dim]")

        if total_proto == 0:
            console.print("    [dim]No results yet.[/dim]")
        console.print()

    # Also show standalone / orphaned results at project level
    proj_results = proj / "results"
    if proj_results.exists():
        orphaned = sorted(proj_results.glob("*"))
        orphaned = [f for f in orphaned if f.is_file() and f.suffix in (".pdf", ".svg", ".png")]
        direct_results = [f for f in orphaned if not any(f.name.startswith(py.stem) for py in proto_yamls)]
        if direct_results:
            console.print("  [bold]Other results:[/bold]")
            for f in direct_results:
                size = f.stat().st_size
                console.print(f"    [dim]• {f.name}  ({_fmt_size(size)})[/dim]")
            console.print()


def _fmt_size(bytes: int) -> str:
    if bytes < 1024:
        return f"{bytes}B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.0f}KB"
    else:
        return f"{bytes / 1024 ** 2:.1f}MB"

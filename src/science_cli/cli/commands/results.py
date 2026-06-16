"""results command — list saved figures/analysis by protocol and step."""

import json
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

    # Check for --star / star subcommand (toggle star on results)
    if any(a in ("--star", "star") for a in args):
        _results_star(args)
        return

    # Check for --move / -m flag (symlink mode)
    if any(a in ("--move", "-m") for a in args):
        _results_move(args)
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


# ── Star/highlight system ────────────────────────────────────


def _stars_path(proj: Path) -> Path:
    """Return path to the star state file for a project."""
    return proj / "results" / ".stars.json"


def _load_stars(proj: Path) -> dict[str, bool]:
    """Load the star dict (rel_key → bool) for a project."""
    sp = _stars_path(proj)
    if sp.exists():
        try:
            return json.loads(sp.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_stars(proj: Path, stars: dict[str, bool]) -> None:
    """Persist the star dict to project/results/.stars.json."""
    sp = _stars_path(proj)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(stars, indent=2))


def _results_star(args: list) -> None:
    """Toggle star on result files via fzf multi-select."""
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.fzf_utils import fzf_select

    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    paths = ProjectPaths(proj)
    result_files: list[tuple[str, str, Path]] = []
    for py in paths.list_protocol_yamls():
        pname = py.stem
        proto_path = paths.protocol_subdir(pname)
        if proto_path.exists():
            for sd in sorted(proto_path.iterdir()):
                if not sd.is_dir():
                    continue
                results_dir = sd / "results"
                if results_dir.exists():
                    for pf in sorted(results_dir.iterdir()):
                        if pf.suffix in (".pdf", ".svg", ".png", ".csv", ".json", ".txt"):
                            result_files.append((pname, sd.name, pf))

    if not result_files:
        console.print("[yellow]No result files found.[/yellow]")
        return

    stars = _load_stars(proj)

    # Build fzf display lines with star indicator
    display_lines = []
    for pname, sd_name, pf in result_files:
        rel_key = f"{pname}/{sd_name}/{pf.name}"
        prefix = "⭐ " if stars.get(rel_key, False) else ""
        display_lines.append(f"{prefix}{pf.name:<45} {pname:<22} {sd_name}")

    selected = fzf_select(display_lines, prompt="Toggle star on results (multi):", multi=True)
    if not selected:
        return

    toggled = 0
    for line in selected:
        for pname, sd_name, pf in result_files:
            rel_key = f"{pname}/{sd_name}/{pf.name}"
            if pf.name in line and pname in line and sd_name in line:
                stars[rel_key] = not stars.get(rel_key, False)
                toggled += 1
                break

    _save_stars(proj, stars)
    console.print(f"[green]✓[/green] Toggled star for {toggled} files.")


def _results_move(args: list) -> None:
    """Select results via fzf and create symlinks in project/results/.

    Originals stay in their protocol/step/results/ directories.
    Symlinks are collected in project/results/ for unified browsing.
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.fzf_utils import fzf_select, build_fzf_display

    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    paths = ProjectPaths(proj)
    result_files = []
    for py in paths.list_protocol_yamls():
        pname = py.stem
        proto_path = paths.protocol_subdir(pname)
        if proto_path.exists():
            for sd in sorted(proto_path.iterdir()):
                if not sd.is_dir():
                    continue
                results_dir = sd / "results"
                if results_dir.exists():
                    for pf in sorted(results_dir.iterdir()):
                        if pf.suffix in (".pdf", ".svg", ".png", ".csv", ".json", ".txt"):
                            result_files.append((pname, sd.name, pf))

    if not result_files:
        console.print("[yellow]No result files found.[/yellow]")
        return

    stars = _load_stars(proj)

    display_lines = []
    for pname, sd_name, pf in result_files:
        rel_key = f"{pname}/{sd_name}/{pf.name}"
        prefix = "⭐ " if stars.get(rel_key, False) else ""
        display_lines.append(prefix + build_fzf_display(pname, sd_name, pf.name))

    selected = fzf_select(display_lines, prompt="Select results to symlink:", multi=True)
    if not selected:
        return

    to_select = []
    for line in selected:
        line = line.strip()
        # Strip star prefix if present
        if line.startswith("⭐ "):
            clean = line[2:].strip()
        else:
            clean = line
        for pname, sd_name, pf in result_files:
            if build_fzf_display(pname, sd_name, pf.name) == clean:
                to_select.append((pname, sd_name, pf))
                break

    dest_dir = proj / "results"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for pname, sd_name, pf in to_select:
        link_path = dest_dir / pf.name
        if link_path.exists():
            stem = link_path.stem
            suffix = link_path.suffix
            counter = 1
            while link_path.exists():
                link_path = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1
        link_path.symlink_to(pf)
        console.print(f"  [dim]Symlink: {link_path.name} → {pf}[/dim]")

    console.print(f"[green]✓[/green] {len(to_select)} symlinks created in {dest_dir}")

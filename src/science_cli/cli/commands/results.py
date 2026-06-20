"""results command — list saved figures/analysis by protocol and step."""

import subprocess
from pathlib import Path

from rich.console import Console

from science_cli.cli.help import show_command_help
from science_cli.cli.commands.results_status import (
    STATUS_TAGS,
    load_status,
    save_status,
)
from science_cli.core.fzf.columns import status_badge_for_file

console = Console()


def _build_file_step_map(proj: Path) -> dict[str, tuple[str, str, str]]:
    """Build filename → (protocol, step, study) mapping from protocol YAMLs."""
    from science_cli.core.paths import ProjectPaths
    mapping: dict[str, tuple[str, str, str]] = {}
    paths = ProjectPaths(proj)
    for py in paths.list_protocol_yamls():
        pname = py.stem
        import yaml
        with open(py) as f:
            proto_data = yaml.safe_load(f) or {}
        for s in proto_data.get("steps", []):
            study = s.get("study", "")
            for entry in s.get("files", []):
                fname = entry["file"] if isinstance(entry, dict) else entry
                mapping[fname] = (pname, s["name"], study)
    return mapping


def results_handler(args: list) -> None:
    if args and args[0] in ("--help", "-h"):
        show_command_help("results")
        return

    # Check for --star / star subcommand (legacy, maps to status toggle)
    if any(a in ("--star", "star") for a in args):
        _results_status(args)
        return

    # Check for --status <tag> subcommand
    if "--status" in args:
        _results_status(args)
        return

    # Check for --move / -m flag (symlink mode)
    if any(a in ("--move", "-m") for a in args):
        _results_move(args)
        return

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

    # Collect all result files as structured tuples
    result_files: list[tuple[str, str, Path]] = []
    for py in proto_yamls:
        pname = py.stem
        proto_path = paths.protocol_subdir(pname)
        if proto_path.exists():
            for sd in sorted(proto_path.iterdir()):
                if not sd.is_dir():
                    continue
                results_dir = sd / "results"
                if results_dir.exists():
                    for pf in sorted(results_dir.iterdir()):
                        if pf.suffix in (".pdf", ".svg", ".png"):
                            result_files.append((pname, sd.name, pf))

    # FZF mode — pipe results through fzf for interactive opening
    if not result_files:
        console.print("[yellow]No result files found.[/yellow]")
        return
    from science_cli.core.fzf.display import build_fzf_display, fzf_select
    from science_cli.core.project import get_current_project_path as _proj
    status = load_status(_proj())
    file_step_map = _build_file_step_map(_proj()) if _proj() else {}
    display_lines = []
    for pname, sd_name, pf in result_files:
        rel_key = f"{pname}/{sd_name}/{pf.name}"
        badge = status_badge_for_file(rel_key, status)
        _, _, study = file_step_map.get(pf.name, ("", "", ""))
        display_lines.append(
            build_fzf_display(
                pname, sd_name, pf.name,
                width_proto=22, width_step=18,
                study_name=study, status_badge=badge,
            )
        )
    selected = fzf_select(display_lines, prompt="Select result to open:", multi=False)
    if selected:
        for pname, sd_name, pf in result_files:
            rel_key = f"{pname}/{sd_name}/{pf.name}"
            badge = status_badge_for_file(rel_key, status)
            _, _, study = file_step_map.get(pf.name, ("", "", ""))
            if build_fzf_display(
                pname, sd_name, pf.name,
                width_proto=22, width_step=18,
                study_name=study, status_badge=badge,
            ) == selected[0]:
                subprocess.run(["open", str(pf)], check=False)
                console.print(f"[dim]Opened: {pf.name}[/dim]")
                break


def _fmt_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes}B"
    elif nbytes < 1024 ** 2:
        return f"{nbytes / 1024:.0f}KB"
    else:
        return f"{nbytes / 1024 ** 2:.1f}MB"


# ── Status tag system ───────────────────────────────────────


def _results_status(args: list) -> None:
    """Assign status tag to result files via fzf multi-select."""
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.fzf.display import fzf_select, build_fzf_display

    # Parse --status <tag> from args
    tag = None
    for i, a in enumerate(args):
        if a == "--status" and i + 1 < len(args):
            tag = args[i + 1].lower()
            break

    if tag and tag not in (*STATUS_TAGS, "clear"):
        console.print(
            f"[red]Invalid tag '{tag}'. Allowed: {', '.join(STATUS_TAGS)}, clear[/red]"
        )
        return

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

    status = load_status(proj)
    file_step_map = _build_file_step_map(proj)

    # Build fzf display lines with status indicator
    display_lines = []
    for pname, sd_name, pf in result_files:
        rel_key = f"{pname}/{sd_name}/{pf.name}"
        badge = status_badge_for_file(rel_key, status)
        _, _, study = file_step_map.get(pf.name, ("", "", ""))
        display_lines.append(
            build_fzf_display(
                pname, sd_name, pf.name,
                show_protocol=False,
                study_name=study, status_badge=badge,
            )
        )

    selected = fzf_select(
        display_lines, prompt="Set status on results (multi):", multi=True
    )
    if not selected:
        return

    updated = 0
    for line in selected:
        for pname, sd_name, pf in result_files:
            rel_key = f"{pname}/{sd_name}/{pf.name}"
            _, _, study = file_step_map.get(pf.name, ("", "", ""))
            badge = status_badge_for_file(rel_key, status)
            if build_fzf_display(
                pname, sd_name, pf.name,
                show_protocol=False,
                study_name=study, status_badge=badge,
            ).strip() == line.strip():
                if tag == "clear":
                    status.pop(rel_key, None)
                elif tag:
                    status[rel_key] = tag
                else:
                    # Toggle: cycle through star → highlight → discard → (clear)
                    current = status.get(rel_key, "")
                    cycle = ["", "star", "highlight", "discard"]
                    idx = cycle.index(current) if current in cycle else 0
                    next_idx = (idx + 1) % len(cycle)
                    if cycle[next_idx]:
                        status[rel_key] = cycle[next_idx]
                    else:
                        status.pop(rel_key, None)
                updated += 1
                break

    save_status(proj, status)
    console.print(f"[green]✓[/green] Updated status for {updated} files.")


def _results_move(args: list) -> None:
    """Select results via fzf and create symlinks in project/results/."""
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.fzf.display import fzf_select, build_fzf_display

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

    status = load_status(proj)
    file_step_map = _build_file_step_map(proj)

    display_lines = []
    for pname, sd_name, pf in result_files:
        rel_key = f"{pname}/{sd_name}/{pf.name}"
        badge = status_badge_for_file(rel_key, status)
        _, _, study = file_step_map.get(pf.name, ("", "", ""))
        display_lines.append(
            build_fzf_display(
                pname, sd_name, pf.name,
                study_name=study, status_badge=badge,
            )
        )

    selected = fzf_select(display_lines, prompt="Select results to symlink:", multi=True)
    if not selected:
        return

    to_select = []
    for line in selected:
        line = line.strip()
        for pname, sd_name, pf in result_files:
            rel_key = f"{pname}/{sd_name}/{pf.name}"
            badge = status_badge_for_file(rel_key, status)
            _, _, study = file_step_map.get(pf.name, ("", "", ""))
            if build_fzf_display(
                pname, sd_name, pf.name,
                study_name=study, status_badge=badge,
            ).strip() == line:
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

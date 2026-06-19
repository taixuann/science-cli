"""Pulse measurement CLI — logic for sci pulse command."""
import argparse
from pathlib import Path

from rich.console import Console

console = Console()


def build_pulse_parser():
    """Build argument parser for pulse subcommands."""
    parser = argparse.ArgumentParser(prog="pulse", description="Pulse measurement analysis commands")
    parser.add_argument("--study", "-s", default="", help="Study name for technique resolution")
    subparsers = parser.add_subparsers(dest="subcommand")

    subparsers.add_parser("ls", help="List pulse measurement files")

    p_list = subparsers.add_parser("list", help="List pulse files with metadata from protocol.yaml")
    p_list.add_argument("--study-filter", "-f", default="", help="Filter by study name (e.g. pulse:pulse-stp-decay)")

    p_overlay = subparsers.add_parser("overlay", help="Overlay pulse files grouped by a metadata variable")
    p_overlay.add_argument("study", nargs="?", default="", help="Study name to overlay (e.g. pulse:pulse-stp-decay)")
    p_overlay.add_argument("--group-by", "-g", default="", help="Group by metadata variable (skip fzf prompt)")
    p_overlay.add_argument("--tolerance", "-t", type=float, default=0.01, help="Grouping tolerance for numeric values")
    p_overlay.add_argument("--output", "-o", default="", help="Output file path (default: auto)")

    p_endurance = subparsers.add_parser("endurance", help="Analyze endurance cycling")
    p_endurance.add_argument("--file", help="Endurance data file")

    p_retention = subparsers.add_parser("retention", help="Analyze retention decay")
    p_retention.add_argument("--file", help="Retention data file")

    p_stp = subparsers.add_parser("stp", help="Analyze STP decay")
    p_stp.add_argument("--file", help="STP decay data file")

    p_ppf = subparsers.add_parser("ppf", help="Analyze PPF ratio")
    p_ppf.add_argument("--file", help="PPF data file")

    subparsers.add_parser("dashboard", help="Launch pulse dashboard")

    return parser


def _resolve_project_root() -> Path | None:
    """Resolve the current project root from session."""
    try:
        from science_cli.core.session import load_session
        sess = load_session()
        last_proj = sess.get("last_project", "")
        if last_proj:
            p = Path(last_proj)
            if p.exists():
                return p
    except Exception:
        pass
    # Fallback: try current working directory
    cwd = Path.cwd()
    if (cwd / "protocol.yaml").exists():
        return cwd
    return None


def cmd_ls(args):
    console.print("[dim]Pulse measurement files:[/dim]")


def cmd_endurance(args):
    console.print("[yellow]endurance analysis not yet implemented[/yellow]")


def cmd_list(args):
    """List pulse files from protocol.yaml with metadata."""
    from science_cli.core.protocol import get_pulse_steps_with_metadata
    from science_cli.core.fzf_utils import build_fzf_display, fzf_select

    project_root = _resolve_project_root()
    if project_root is None:
        console.print("[red]No project found. Use 'sci open' or run from a project directory.[/red]")
        return

    study_filter = getattr(args, "study_filter", "") or ""
    steps = get_pulse_steps_with_metadata(project_root, study_filter)

    if not steps:
        console.print("[yellow]No pulse steps found in protocol.yaml[/yellow]")
        return

    # Build fzf display lines with metadata columns
    display_lines = []
    meta_keys = ["v_set_v", "v_read_v", "set_width_us", "read_width_us", "repeat_pattern"]
    header = build_fzf_display(
        protocol="", step="STEP", filename="FILES",
        show_protocol=False,
        metadata={k: k for k in meta_keys},
        width_meta=16,
    )
    display_lines.append(header)

    for step in steps:
        files = step.get("files", [])
        file_list = ", ".join(
            f.get("file", f) if isinstance(f, dict) else str(f)
            for f in files[:3]
        )
        if len(files) > 3:
            file_list += f" (+{len(files) - 3} more)"

        meta = step.get("metadata", {})
        display_meta = {k: meta.get(k, "") for k in meta_keys}
        line = build_fzf_display(
            protocol="", step=step["name"], filename=file_list,
            show_protocol=False, metadata=display_meta, width_meta=16,
        )
        display_lines.append(line)

    selected = fzf_select(
        display_lines[1:],
        prompt="Select pulse step:",
        multi=True,
        header=display_lines[0],
    )

    if not selected:
        return

    # Print selected steps with full metadata
    for sel in selected:
        for step in steps:
            files = step.get("files", [])
            file_list = ", ".join(
                f.get("file", f) if isinstance(f, dict) else str(f)
                for f in files
            )
            meta = step.get("metadata", {})
            display_meta = {k: meta.get(k, "") for k in meta_keys}
            line = build_fzf_display(
                protocol="", step=step["name"], filename=file_list,
                show_protocol=False, metadata=display_meta, width_meta=16,
            )
            if line.strip() == sel.strip():
                console.print(f"\n[bold cyan]{step['name']}[/bold cyan] ({step['study']})")
                console.print(f"  Files: {file_list}")
                if meta:
                    for k, v in meta.items():
                        console.print(f"  {k}: {v}")
                break


def cmd_overlay(args):
    """Overlay pulse files grouped by a chosen metadata variable."""
    from science_cli.core.protocol import get_pulse_steps_with_metadata

    project_root = _resolve_project_root()
    if project_root is None:
        console.print("[red]No project found. Use 'sci open' or run from a project directory.[/red]")
        return

    study = getattr(args, "study", "") or ""
    if not study:
        # List available pulse studies for selection
        steps = get_pulse_steps_with_metadata(project_root)
        studies = sorted(set(s["study"] for s in steps))
        if not studies:
            console.print("[yellow]No pulse studies found in protocol.yaml[/yellow]")
            return
        from science_cli.core.fzf_utils import fzf_select
        selected = fzf_select(studies, prompt="Select study to overlay:")
        if not selected:
            return
        study = selected[0]

    steps = get_pulse_steps_with_metadata(project_root, study)
    if not steps:
        console.print(f"[yellow]No steps found for study '{study}'[/yellow]")
        return

    # Collect all unique metadata keys across steps
    all_keys: set[str] = set()
    for step in steps:
        all_keys.update(step.get("metadata", {}).keys())

    if not all_keys:
        console.print("[yellow]No metadata found on steps — cannot group. Run 'sci analyze' first.[/yellow]")
        return

    # Select grouping variable
    group_by = getattr(args, "group_by", "") or ""
    if not group_by:
        from science_cli.core.fzf_utils import fzf_select
        sorted_keys = sorted(all_keys)
        selected = fzf_select(sorted_keys, prompt="Group by variable:")
        if not selected:
            return
        group_by = selected[0]

    tolerance = getattr(args, "tolerance", 0.01) or 0.01

    # Group steps by the chosen variable
    groups = _group_steps_by_variable(steps, group_by, tolerance)

    if not groups:
        console.print(f"[yellow]No groups found for variable '{group_by}'[/yellow]")
        return

    console.print(f"\n[bold]Overlay: {study}[/bold]")
    console.print(f"Grouped by: [cyan]{group_by}[/cyan] (tolerance={tolerance})")

    for group_val, group_steps in sorted(groups.items()):
        step_names = [s["name"] for s in group_steps]
        console.print(f"  [{group_val}] {', '.join(step_names)}")

    # Generate overlay plot
    output_path = getattr(args, "output", "") or ""
    _generate_overlay_plot(project_root, study, groups, group_by, output_path)


def _group_steps_by_variable(
    steps: list[dict], variable: str, tolerance: float = 0.01
) -> dict[str, list[dict]]:
    """Group steps by a metadata variable value with numeric tolerance.

    Parameters
    ----------
    steps:
        List of step dicts with ``metadata`` field.
    variable:
        Metadata key to group by.
    tolerance:
        For numeric values, values within ±tolerance are grouped together.

    Returns
    -------
    dict
        Mapping of string group label → list of step dicts.
    """
    groups: dict[str, list[dict]] = {}

    # First pass: collect all values
    raw_values: list[tuple[str, float | str]] = []
    for step in steps:
        meta = step.get("metadata", {})
        val = meta.get(variable)
        if val is None:
            continue
        try:
            num_val = float(val)
            raw_values.append((step["name"], num_val))
        except (TypeError, ValueError):
            raw_values.append((step["name"], str(val)))

    # Check if all values are numeric
    numeric_vals = [v for _, v in raw_values if isinstance(v, float)]

    if len(numeric_vals) == len(raw_values) and numeric_vals:
        # Numeric grouping with tolerance
        sorted_vals = sorted(set(numeric_vals))
        centroids: list[float] = []
        for v in sorted_vals:
            merged = False
            for i, c in enumerate(centroids):
                if abs(v - c) <= tolerance:
                    merged = True
                    break
            if not merged:
                centroids.append(v)

        # Assign steps to centroid groups
        for step_name, val in raw_values:
            best_centroid = min(centroids, key=lambda c: abs(val - c))
            label = f"{best_centroid}"
            groups.setdefault(label, [])
            for step in steps:
                if step["name"] == step_name:
                    groups[label].append(step)
                    break
    else:
        # String grouping (exact match)
        for step_name, val in raw_values:
            label = str(val)
            groups.setdefault(label, [])
            for step in steps:
                if step["name"] == step_name:
                    groups[label].append(step)
                    break

    return groups


def _generate_overlay_plot(
    project_root: Path,
    study: str,
    groups: dict[str, list[dict]],
    group_by: str,
    output_path: str = "",
) -> None:
    """Generate an overlay plot for grouped pulse data.

    Reads CSV data files, overlays them colored by group, and saves to file.
    """
    import csv

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        console.print("[red]matplotlib not available — cannot generate overlay plot[/red]")
        return

    # Determine study technique for column detection
    technique = study.split(":")[0] if ":" in study else "pulse"
    is_stp = "stp" in study.lower()
    is_retention = "retention" in study.lower()

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.tab10.colors

    plot_count = 0
    for group_idx, (group_label, group_steps) in enumerate(sorted(groups.items())):
        color = colors[group_idx % len(colors)]

        for step in group_steps:
            files = step.get("files", [])
            for file_entry in files:
                fname = file_entry.get("file", file_entry) if isinstance(file_entry, dict) else file_entry
                csv_path = project_root / "data" / "raw" / fname
                if not csv_path.exists():
                    # Try step subdirectory
                    csv_path = project_root / "data" / "raw" / step["name"] / fname
                if not csv_path.exists():
                    continue

                try:
                    time_col, data_col = _detect_columns(csv_path, is_stp, is_retention)
                    if time_col is None or data_col is None:
                        continue

                    times, values = _read_csv_columns(csv_path, time_col, data_col)
                    if not times:
                        continue

                    label = f"{group_by}={group_label}" if plot_count == 0 or group_idx == 0 else ""
                    ax.plot(times, values, color=color, alpha=0.7, linewidth=1,
                            label=label if label else None)
                    plot_count += 1
                except Exception:
                    continue

    if plot_count == 0:
        console.print("[yellow]No data files found to plot[/yellow]")
        plt.close(fig)
        return

    ax.set_xlabel("Time")
    ax.set_ylabel("Current" if is_stp else "Resistance")
    ax.set_title(f"Overlay: {study} (grouped by {group_by})")
    ax.grid(True, alpha=0.3)

    # Deduplicate legend entries
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    if by_label:
        ax.legend(by_label.values(), by_label.keys())

    if not output_path:
        output_path = str(project_root / "results" / f"overlay_{study.replace(':', '_')}_{group_by}.png")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Overlay saved: {out}[/green]")


def _detect_columns(
    csv_path: Path, is_stp: bool = False, is_retention: bool = False
) -> tuple[str | None, str | None]:
    """Auto-detect time and data columns from CSV header."""
    try:
        with open(csv_path) as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None, None
            header = [h.strip() for h in header]
    except Exception:
        return None, None

    time_col = None
    data_col = None

    for h in header:
        hl = h.lower()
        if time_col is None and ("time" in hl or "t (ms)" in hl or "t (s)" in hl):
            time_col = h
        if is_stp and data_col is None and "current" in hl:
            data_col = h
        elif is_retention and data_col is None and ("resistance" in hl or "r (" in hl):
            data_col = h
        elif data_col is None and ("current" in hl or "resistance" in hl or "value" in hl):
            data_col = h

    # Fallback: first column = time, second = data
    if time_col is None and len(header) >= 2:
        time_col = header[0]
    if data_col is None and len(header) >= 2:
        data_col = header[1]

    return time_col, data_col


def _read_csv_columns(
    csv_path: Path, time_col: str, data_col: str
) -> tuple[list[float], list[float]]:
    """Read two columns from CSV, returning float lists."""
    times: list[float] = []
    values: list[float] = []
    try:
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    t = float(row.get(time_col, "nan"))
                    v = float(row.get(data_col, "nan"))
                    if not (t != t or v != v):  # skip NaN
                        times.append(t)
                        values.append(v)
                except (ValueError, TypeError):
                    continue
    except Exception:
        pass
    return times, values


def cmd_retention(args):
    console.print("[yellow]retention analysis not yet implemented[/yellow]")


def cmd_stp(args):
    console.print("[yellow]STP analysis not yet implemented[/yellow]")


def cmd_ppf(args):
    console.print("[yellow]PPF analysis not yet implemented[/yellow]")


def cmd_dashboard(args):
    console.print("[yellow]dashboard not yet implemented[/yellow]")


def show_pulse_help():
    parser = build_pulse_parser()
    parser.print_help()

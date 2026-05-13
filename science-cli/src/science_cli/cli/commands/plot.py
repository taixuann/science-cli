"""plot command handler — interactive fzf or direct, with hints."""

from pathlib import Path
from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help
from science_cli.core.session import get_active_theme
from science_cli.core.file_utils import is_flag
from science_cli.theme import apply_theme

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


def _resolve_file(name: str) -> str:
    path = Path(name)
    if path.exists():
        return str(path)
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if proj:
        raw_dir = proj / "data" / "raw"
        full = raw_dir / name
        if full.exists():
            return str(full)
        for f in raw_dir.iterdir():
            if name.lower() in f.name.lower():
                return str(f)
    return ""


def _detect_technique(filename: str) -> str:
    from science_cli.core.technique import detect_technique
    t = detect_technique(filename)
    return t.lower() if t else ""


def _get_results_dir(filepath: str) -> Path:
    """Determine results dir: protocol/<step>/results/ if in session, else project/results/."""
    from science_cli.core.session import load_session
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    session = load_session()
    current_protocol = session.get("last_protocol")
    proj = get_current_project_path()
    if current_protocol and proj:
        paths = ProjectPaths(proj)
        pname = session.get("last_protocol", "")
        yaml_path = paths.protocol_yaml(pname)
        if yaml_path.exists():
            import yaml
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            fname = Path(filepath).name
            for s in data.get("steps", []):
                step_files = s.get("files", [])
                norm = [e["file"] if isinstance(e, dict) else e for e in step_files]
                if fname in norm:
                    results_dir = paths.step_results_dir(pname, s["name"])
                    results_dir.mkdir(parents=True, exist_ok=True)
                    return results_dir
    if proj:
        out = proj / "results"
    else:
        out = Path(filepath).parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _technique_hints(technique: str) -> dict:
    """Return contextual hints for a technique. Keys: plot_style, figure."""
    hints = {
        "ec-cv": {
            "plot_style": "--peaks (find redox peaks) | --charge (integrate charge) | --zoom x1,x2,y1,y2",
            "figure": "-n cv_plot.pdf | --grid (show grid) | --legend (show legend)",
        },
        "ec-ca": {
            "plot_style": "--fit (Cottrell fit) | --zoom x1,x2,y1,y2",
            "figure": "-n ca_decay.pdf | --label-name 0V,0.25V,... | --grid | --legend",
        },
        "ec-eis": {
            "plot_style": "--nyquist (Z' vs -Z'') | --bode (|Z|, phase vs f) | --circuit (fit circuit) | --kk (K-K check)",
            "figure": "-n nyquist.pdf | --grid | --legend",
        },
        "iv-sweep": {
            "plot_style": "--type line|scatter | --color | --linewidth | --linestyle",
            "figure": "-n iv_curve.pdf | --label-name label1,label2,... | --xlabel Voltage (V) | --ylabel Current (A) | --zoom x1,x2,y1,y2",
        },
        "iv-breakdown": {
            "plot_style": "--type line | --color | --linewidth",
            "figure": "-n breakdown.pdf | --label-name label1,label2,... | --xlabel Voltage (V) | --ylabel Current (A) | --zoom x1,x2,y1,y2",
        },
        "iv-leakage": {
            "plot_style": "--type line | --color | --linewidth",
            "figure": "-n leakage.pdf | --xlabel Voltage (V) | --ylabel |Current| (A) | --zoom x1,x2,y1,y2",
        },
        "mem-endurance": {
            "plot_style": "--type line|scatter | --color | --linewidth",
            "figure": "-n endurance.pdf | --xlabel Cycle # | --ylabel Resistance (Ω) | --zoom x1,x2,y1,y2",
        },
        "mem-retention": {
            "plot_style": "--type line | --color | --linewidth",
            "figure": "-n retention.pdf | --xlabel Time (s) | --ylabel Resistance (Ω) | --zoom x1,x2,y1,y2",
        },
        "mem-switching": {
            "plot_style": "--type scatter | --color | --marker o | --markersize",
            "figure": "-n switching.pdf | --xlabel Cycle # | --ylabel Voltage (V) | --zoom x1,x2,y1,y2",
        },
    }
    return hints.get(technique, hints.get("", {}))


def _plot_results() -> None:
    """List all saved results/figures organized by protocol and step."""
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    from science_cli.core.session import load_session
    from science_cli.core.paths import ProjectPaths
    active_protocol = load_session().get("last_protocol", "")
    paths = ProjectPaths(proj)

    rprint(f"\n[bold]Saved figures[/bold] — {proj.name}\n")

    total = 0

    # Per-step results inside protocol directories
    proto_dirs = paths.list_protocol_yamls()
    for py in proto_dirs:
        pname = py.stem
        proto_subdir = paths.protocol_subdir(pname)
        if not proto_subdir.exists():
            continue
        protocol_marker = " [green]← active[/green]" if active_protocol == pname else ""
        rprint(f"  [bold cyan]{pname}[/bold cyan]{protocol_marker}")
        step_count = 0
        for step_dir in sorted(proto_subdir.iterdir()):
            if not step_dir.is_dir():
                continue
            results_dir = step_dir / "results"
            if not results_dir.exists():
                continue
            figures = sorted(results_dir.glob("*"))
            figures = [f for f in figures if f.is_file() and f.suffix in (".pdf", ".svg", ".png")]
            if not figures:
                continue
            for f in figures:
                size = f.stat().st_size
                rprint(f"    [dim]•[/dim] {step_dir.name}/{f.name} [dim]({_fmt_size(size)})[/dim]")
                total += 1
                step_count += 1
        if step_count == 0:
            rprint(f"    [dim]No step-level results.[/dim]")

    # Project-level results (categorized by protocol if possible)
    out_dir = proj / "results"
    if out_dir.exists():
        project_figs = sorted(out_dir.glob("*"))
        project_figs = [f for f in project_figs if f.is_file() and f.suffix in (".pdf", ".svg", ".png")]
        project_figs = [f for f in project_figs if not any(
            f.name.startswith(p.stem) for p in proto_dirs
        )]
        if project_figs:
            rprint(f"  [bold]Project root:[/bold]")
            for f in project_figs:
                size = f.stat().st_size
                rprint(f"    [dim]•[/dim] {f.name} [dim]({_fmt_size(size)})[/dim]")
                total += 1

    if total == 0:
        rprint("  [yellow]No saved figures yet.[/yellow]")

    rprint(f"\n[bold]Total:[/bold] {total} figure(s)")
    rprint("[dim]Use 'plot open <name>' to view, 'plot delete <name>' to remove.[/dim]")


def _plot_open(name: str) -> None:
    """Open a saved figure with system viewer."""
    if not name:
        console.print("[yellow]Usage: plot open <filename>[/yellow]")
        return
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return
    candidate = proj / "results" / name
    if not candidate.exists():
        # Try fuzzy match
        matches = list((proj / "results").glob(f"*{name}*"))
        if len(matches) == 1:
            candidate = matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches for '{name}':[/yellow]")
            for m in matches:
                console.print(f"  [dim]•[/dim] {m.name}")
            return
        else:
            console.print(f"[red]Figure '{name}' not found in results/.[/red]")
            return
    import subprocess
    subprocess.run(["open", str(candidate)])
    console.print(f"[bold green]✓[/bold green] Opened: {candidate.name}")


def _plot_delete(name: str) -> None:
    """Delete a saved figure."""
    if not name:
        console.print("[yellow]Usage: plot delete <filename>[/yellow]")
        return
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return
    candidate = proj / "results" / name
    if not candidate.exists():
        matches = list((proj / "results").glob(f"*{name}*"))
        if len(matches) == 1:
            candidate = matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches for '{name}':[/yellow]")
            for m in matches:
                console.print(f"  [dim]•[/dim] {m.name}")
            return
        else:
            console.print(f"[red]Figure '{name}' not found in results/.[/red]")
            return
    import questionary
    if questionary.confirm(f"Delete '{candidate.name}'?", default=False).ask():
        candidate.unlink()
        console.print(f"[bold green]✓[/bold green] Deleted: {candidate.name}")
    else:
        console.print("[yellow]Cancelled.[/yellow]")


def _fmt_size(bytes: int) -> str:
    if bytes < 1024:
        return f"{bytes}B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.0f}KB"
    else:
        return f"{bytes / 1024 ** 2:.1f}MB"


def plot_handler(args: list) -> None:
    if not args:
        _plot_interactive()
        return
    if args[0] in ("--help", "-h"):
        show_command_help("plot")
        return
    if args[0] == "-theme":
        from science_cli.theme import list_themes, apply_theme
        from science_cli.core.session import get_active_theme, set_active_theme
        active = get_active_theme()
        themes = list_themes()
        rprint(f"[bold]Current theme:[/bold] {active}")
        rprint(f"[dim]Use 'config theme set <name>' to change.[/dim]")
        rprint(f"[dim]Available: {', '.join(themes)}[/dim]")
        return
    if args[0] == "--fzf":
        _plot_interactive()
        return

    if args[0] == "results":
        _plot_results()
        return
    if args[0] == "open":
        _plot_open(args[1] if len(args) > 1 else "")
        return
    if args[0] == "delete":
        _plot_delete(args[1] if len(args) > 1 else "")
        return

    if args[0] == "-f":
        files_str = args[1] if len(args) > 1 else ""
        rest = args[2:] if len(args) > 2 else []
        files = [f.strip() for f in files_str.split(",") if f.strip()]
        _plot_direct(files, rest)
    else:
        console.print("[yellow]Usage: plot [--fzf | -f file1,file2 [options]][/yellow]")


def _plot_interactive() -> None:
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    raw_dir = proj / "data" / "raw"
    if not raw_dir.exists():
        console.print(f"[red]data/raw/ not found.[/red]")
        return

    files = sorted(raw_dir.iterdir())
    if not files:
        console.print("[yellow]No files in data/raw/[/yellow]")
        return

    from science_cli.core.fzf_utils import fzf_select
    import re

    item_names = [f.name for f in files]

    # Build file-to-step mapping from all protocols
    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    file_step_map: dict[str, tuple[str, str]] = {}
    for py in paths.list_protocol_yamls():
        pname = py.stem
        with open(py) as f:
            proto_data = __import__("yaml").safe_load(f) or {}
        for s in proto_data.get("steps", []):
            for entry in s.get("files", []):
                fname = entry["file"] if isinstance(entry, dict) else entry
                file_step_map[fname] = (pname, s["name"])

    # Build display items with step/protocol info
    marker_re = re.compile(r"\s+→ .*$")
    display_items = []
    for name in item_names:
        if name in file_step_map:
            proto, step = file_step_map[name]
            display_items.append(f"{name} → {proto}/{step}")
        else:
            display_items.append(name)

    selected = fzf_select(
        items=display_items,
        prompt="Select file(s) (Tab to multi-select):",
        multi=True,
        preview=f"head -n 20 {raw_dir}/$(echo {{}} | cut -d' ' -f1)",
        preview_window="right:50%:border-sharp",
    )
    if not selected:
        return

    # Strip step info to get clean filenames
    selected = [marker_re.sub("", s) for s in selected]

    # Show selected files summary
    rprint(f"\n[bold]Selected {len(selected)} file(s):[/bold]")
    for f in selected:
        step_info = ""
        if f in file_step_map:
            proto, step = file_step_map[f]
            step_info = f"  [dim]→ {proto}/{step}[/dim]"
        rprint(f"  [dim]• {f}[/dim]{step_info}")
    rprint("")

    # Auto-detect technique from open protocol
    from science_cli.core.session import load_session
    session = load_session()
    current_protocol = session.get("last_protocol", "")
    auto_technique = ""
    if current_protocol and proj:
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(proj)
        proto_yaml = paths.protocol_yaml(current_protocol)
        if proto_yaml.exists():
            import yaml
            with open(proto_yaml) as f:
                proto_data = yaml.safe_load(f) or {}
            file_to_tech = {}
            for s in proto_data.get("steps", []):
                for entry in s.get("files", []):
                    fname = entry["file"] if isinstance(entry, dict) else entry
                    file_to_tech[fname] = s.get("technique", "")
            detected = set(file_to_tech.get(f, "") for f in selected)
            if len(detected) == 1:
                auto_technique = detected.pop()
    # Fallback: detect from first filename
    if not auto_technique and selected:
        auto_technique = _detect_technique(selected[0])

    # Pre-fill flags from technique template
    all_flags: dict = {}
    if auto_technique:
        from science_cli.theme import template_to_flags
        all_flags.update(template_to_flags(auto_technique))

    # Apply active theme defaults
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    if auto_technique:
        rprint(f"  [bold]Detected technique:[/bold] {auto_technique}")
        if all_flags:
            rprint(f"  [bold]Pre-filled defaults:[/bold] [dim]{all_flags}[/dim]")

    # Prompt 1: Style / analysis flags
    style_hint = _technique_hints(auto_technique).get(
        "plot_style",
        "--type line|scatter | --color | --linewidth | --linestyle | --marker | --markersize",
    )
    rprint(f"  [dim]# {style_hint}[/dim]")
    raw_style = input("  Style / analysis options (Enter to skip — uses theme defaults): ").strip()
    if raw_style:
        _, style_flags = _parse_flags(raw_style.split())
        all_flags.update(style_flags)

    # Prompt 2: Figure / output flags
    fig_hint = _technique_hints(auto_technique).get(
        "figure",
        "-n name.pdf|png|svg | --label-name n1,n2,... | --title | --xlabel | --ylabel | --xlim | --ylim | --zoom x1,x2,y1,y2 | --size | --dpi | --grid | --legend",
    )
    rprint(f"  [dim]# {fig_hint}[/dim]")
    raw_figure = input("  Figure options (Enter to skip — uses theme defaults): ").strip()
    if raw_figure:
        _, figure_flags = _parse_flags(raw_figure.split())
        all_flags.update(figure_flags)

    resolved = [_resolve_file(f) for f in selected]
    resolved = [f for f in resolved if f]

    if len(resolved) == 1:
        _do_plot(resolved[0], all_flags, auto_technique)
    elif len(resolved) > 1:
        _do_overlap(resolved, all_flags, auto_technique)
    else:
        console.print("[yellow]No valid files selected.[/yellow]")


def _plot_direct(files: list, rest_args: list) -> None:
    _, flags = _parse_flags(rest_args)

    resolved = [_resolve_file(f) for f in files]
    resolved = [f for f in resolved if f]

    if not resolved:
        console.print("[red]File(s) not found.[/red]")
        return

    if len(resolved) == 1:
        _do_plot(resolved[0], flags)
    else:
        _do_overlap(resolved, flags)


def _resolve_xy_columns(
    df: "pd.DataFrame", info: dict, technique: str = ""
) -> tuple:
    """Return (x, y, xlabel, ylabel) based on technique and available columns."""
    import numpy as np

    cols = [c for c in df.columns if c not in ("Index", "index")]
    xcol, ycol = "", ""

    if technique == "ec-ca":
        # CA: time vs current
        for candidate in (
            "Corrected time (s)", "corrected time", "time",
            "Time", "Time (s)", "t/s",
        ):
            if candidate in df.columns:
                xcol = candidate
                break
        for candidate in (
            "WE(1).Current (A)", "Current (A)", "current",
            "I", "I/A", "<I>/A",
        ):
            if candidate in df.columns:
                ycol = candidate
                break

    elif technique == "ec-cv":
        # CV: potential vs current
        for candidate in (
            "WE(1).Potential (V)", "Potential (V)", "potential",
            "Potential applied (V)", "E", "E/V", "V",
        ):
            if candidate in df.columns:
                xcol = candidate
                break
        for candidate in (
            "WE(1).Current (A)", "Current (A)", "current",
            "I", "I/A",
        ):
            if candidate in df.columns:
                ycol = candidate
                break

    elif technique in ("iv-sweep", "iv-breakdown", "iv-leakage"):
        # IV: voltage vs current
        for candidate in (
            "Voltage (V)", "voltage", "V",
            "WE(1).Potential (V)", "Potential (V)",
            "BV", "Bias Voltage (V)", "bias_voltage",
        ):
            if candidate in df.columns:
                xcol = candidate
                break
        for candidate in (
            "Current (A)", "current", "I", "I/A",
            "WE(1).Current (A)",
            "Bi", "Bias Current (A)", "bias_current",
        ):
            if candidate in df.columns:
                ycol = candidate
                break

    elif technique in ("mem-endurance", "mem-retention"):
        # Endurance/retention: cycle/time vs resistance
        numeric = [
            c
            for c in df.select_dtypes(include=[np.number]).columns
            if c not in ("Index", "index")
        ]
        if len(numeric) >= 2:
            xcol, ycol = numeric[0], numeric[1]

    # Fallback: first two numeric columns
    if not xcol or not ycol:
        numeric = [
            c
            for c in df.select_dtypes(include=[np.number]).columns
            if c not in ("Index", "index")
        ]
        if len(numeric) >= 2:
            xcol, ycol = numeric[0], numeric[1]
        else:
            return np.array([]), np.array([]), "", ""

    x = df[xcol].values
    y = df[ycol].values

    # Time normalization: if x looks like absolute time (large values), subtract min
    if technique in ("ec-ca", "ec-cv", "ec-eis") and xcol not in (
        "Corrected time (s)", "corrected time",
    ):
        x_numeric = np.asarray(x, dtype=float)
        if np.any(x_numeric > 100):
            x = x_numeric - x_numeric[0]

    mask = ~(np.isnan(x.astype(float)) | np.isnan(y.astype(float)))
    return x[mask], y[mask], xcol, ycol


def _do_plot(filepath: str, flags: dict, technique: str = "") -> None:
    from science_cli.core.data_loader import load_data_file

    try:
        df, info = load_data_file(filepath)
    except Exception as e:
        console.print(f"[red]Failed to load file: {e}[/red]")
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    apply_theme(get_active_theme())
    fig, ax = plt.subplots(figsize=_figsize(flags))

    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, technique)
    if len(x) == 0 or len(y) == 0:
        console.print(
            "[red]Could not determine x/y columns for this technique.[/red]"
        )
        return

    # Apply template flags for labels if not overridden by user
    if not flags.get("xlabel") and xlabel:
        flags["xlabel"] = xlabel
    if not flags.get("ylabel") and ylabel:
        flags["ylabel"] = ylabel

    plot_type = flags.get("type", "line")
    color = flags.get("color", None)
    linewidth = float(flags.get("linewidth", 1.5)) if flags.get("linewidth") else 1.5
    linestyle = flags.get("linestyle", "solid")
    marker = flags.get("marker", None)
    markersize = float(flags.get("markersize", 6)) if flags.get("markersize") else 6
    cmap = flags.get("cmap", None)

    plot_kw = {}
    if color:
        plot_kw["color"] = color
    if marker:
        plot_kw["marker"] = marker
        plot_kw["markersize"] = markersize

    if plot_type == "line":
        ax.plot(x, y, linewidth=linewidth, linestyle=linestyle, **plot_kw)
    elif plot_type == "scatter":
        scatter_kw = {}
        if color:
            scatter_kw["c"] = color
        if cmap:
            scatter_kw["cmap"] = cmap
        ax.scatter(x, y, s=markersize ** 2, alpha=0.8, **scatter_kw)
    else:
        ax.plot(x, y, linewidth=linewidth, **plot_kw)

    _apply_figure_kw(ax, flags, Path(filepath).stem)

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    if technique:
        out_name = flags.get("n") or flags.get("name", f"{technique}_{stem}.pdf")
    else:
        out_name = flags.get("n") or flags.get("name", f"{stem}_plot.pdf")
    # Ensure .pdf extension if none specified
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", 150))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")

    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] Plot saved: {save_path}")

    from science_cli.core.manifest import emit_manifest
    from science_cli.core.project import get_current_project_path
    emit_manifest(
        output_dir=out_dir,
        command=f"plot {filepath}",
        source_files=[filepath],
        output_files=[str(save_path)],
        technique=_detect_technique(Path(filepath).name),
        parameters=flags,
        project=get_current_project_path().name if get_current_project_path() else "",
    )


def _do_overlap(files: list, flags: dict, technique: str = "") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from science_cli.core.data_loader import load_data_file

    apply_theme(get_active_theme())
    fig, ax = plt.subplots(figsize=_figsize(flags))
    # Use theme color cycle instead of hardcoded viridis
    import matplotlib as mpl
    cycle = mpl.rcParams["axes.prop_cycle"]
    theme_colors = [entry["color"] for entry in cycle]
    colors = [theme_colors[i % len(theme_colors)] for i in range(len(files))]

    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []

    for i, fp in enumerate(files):
        try:
            df, info = load_data_file(fp)
            xi, yi, _, _ = _resolve_xy_columns(df, info, technique)
            if len(xi) == 0 or len(yi) == 0:
                continue
            label = label_list[i] if i < len(label_list) else Path(fp).stem
            ax.plot(xi, yi, label=label, color=colors[i], linewidth=1.5)
        except Exception:
            continue

    ax.legend()
    _apply_figure_kw(ax, flags, "overlay")

    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", f"{technique}_overlay.pdf" if technique else "overlay.pdf")
    # Ensure .pdf extension if none specified
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", 150))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] Overlay saved: {save_path}")


def _apply_zoom(ax, zoom_str: str) -> None:
    """Parse --zoom x1,x2,y1,y2 and set axis limits. Either x or y part optional."""
    parts = [s.strip() for s in zoom_str.split(",")]
    if not parts:
        return
    try:
        if len(parts) == 2:
            ax.set_xlim(float(parts[0]), float(parts[1]))
        elif len(parts) == 4:
            ax.set_xlim(float(parts[0]), float(parts[1]))
            ax.set_ylim(float(parts[2]), float(parts[3]))
        else:
            console.print(f"[yellow]Usage: --zoom x1,x2 or --zoom x1,x2,y1,y2[/yellow]")
    except (ValueError, IndexError):
        console.print(f"[red]Invalid zoom values: {zoom_str}[/red]")


def _figsize(flags: dict) -> tuple:
    size = flags.get("size", "")
    if size:
        try:
            parts = size.split(",")
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            pass
    return (10, 7)


def _apply_figure_kw(ax, flags: dict, title_default: str) -> None:
    if flags.get("title"):
        ax.set_title(flags["title"])
    if flags.get("xlabel"):
        ax.set_xlabel(flags["xlabel"])
    if flags.get("ylabel"):
        ax.set_ylabel(flags["ylabel"])
    if flags.get("xlim"):
        try:
            parts = flags["xlim"].split(",")
            ax.set_xlim(float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            pass
    if flags.get("ylim"):
        try:
            parts = flags["ylim"].split(",")
            ax.set_ylim(float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            pass
    if flags.get("zoom"):
        _apply_zoom(ax, flags["zoom"])
    if flags.get("grid"):
        ax.grid(True, alpha=0.3)
    if flags.get("legend"):
        ax.legend()
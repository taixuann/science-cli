"""plot command handler — interactive fzf or direct, with hints."""

from pathlib import Path

from rich import print as rprint
from rich.console import Console

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag
from science_cli.core.session import get_active_theme
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
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session
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


TECHNIQUE_HINTS = {
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
    "raman": {
        "plot_style": "--type line | --color | --linewidth",
        "figure": "-n spectrum.pdf | --xlabel 'Raman shift (cm⁻¹)' | --ylabel 'Intensity (counts)' | --grid | --zoom x1,x2",
    },
    "uv-vis": {
        "plot_style": "--type line | --color | --linewidth",
        "figure": "-n uv-vis.pdf | --xlabel 'Wavelength (nm)' | --ylabel 'T%' | --grid | --zoom x1,x2,y1,y2",
    },
}


def _technique_hints(technique: str) -> dict:
    """Return contextual hints for a technique. Keys: plot_style, figure."""
    return TECHNIQUE_HINTS.get(technique, {})


def _plot_results() -> None:
    """List all saved results/figures organized by protocol and step."""
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    from science_cli.core.paths import ProjectPaths
    from science_cli.core.session import load_session
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
            rprint("    [dim]No step-level results.[/dim]")

    # Project-level results (categorized by protocol if possible)
    out_dir = proj / "results"
    if out_dir.exists():
        project_figs = sorted(out_dir.glob("*"))
        project_figs = [f for f in project_figs if f.is_file() and f.suffix in (".pdf", ".svg", ".png")]
        project_figs = [f for f in project_figs if not any(
            f.name.startswith(p.stem) for p in proto_dirs
        )]
        if project_figs:
            rprint("  [bold]Project root:[/bold]")
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
        from science_cli.core.session import get_active_theme
        from science_cli.theme import list_themes
        active = get_active_theme()
        themes = list_themes()
        rprint(f"[bold]Current theme:[/bold] {active}")
        rprint("[dim]Use 'config theme set <name>' to change.[/dim]")
        rprint(f"[dim]Available: {', '.join(themes)}[/dim]")
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

    # Default to fzf interactive with remaining args as extra flags
    _plot_interactive(args)


def _plot_interactive(extra_args: list | None = None) -> None:
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return

    raw_dir = proj / "data" / "raw"
    if not raw_dir.exists():
        console.print("[red]data/raw/ not found.[/red]")
        return

    files = sorted(raw_dir.iterdir())
    if not files:
        console.print("[yellow]No files in data/raw/[/yellow]")
        return

    import re

    from science_cli.core.fzf_utils import fzf_select

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

    from science_cli.core.session import load_session
    sess = load_session()
    active_proto = sess.get("last_protocol", "")
    if active_proto:
        file_step_map = {k: v for k, v in file_step_map.items() if v[0] == active_proto}

    # Build display items with step/protocol info
    from science_cli.core.fzf_utils import build_fzf_display
    show_proto = not active_proto
    col_re = re.compile(r"^\S+\s+\S+\s+") if show_proto else re.compile(r"^\S+\s+")
    display_items = []
    for name in item_names:
        if name in file_step_map:
            proto, step = file_step_map[name]
            display_items.append(build_fzf_display(proto, step, name, show_protocol=show_proto))
        elif not active_proto:
            display_items.append(name)

    prompt = f"{active_proto} | Select file(s) >" if active_proto else "Select file(s) (Tab to multi-select):"
    selected = fzf_select(
        items=display_items,
        prompt=prompt,
        multi=True,
        preview=f"head -n 20 {raw_dir}/$(echo {{}} | awk '{{print $NF}}')",
        preview_window="right:50%:border-sharp",
    )
    if not selected:
        return

    # Strip column prefix to get clean filenames
    selected = [col_re.sub("", s) for s in selected]

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

    if not resolved:
        console.print("[yellow]No valid files selected.[/yellow]")
        return

    # Determine overlay vs individual mode
    overlay_mode = extra_args and "--overlay" in extra_args
    all_mode = extra_args and "--all" in extra_args

    if not overlay_mode and not all_mode and len(resolved) > 1:
        choice = input("  Overlay all (o) or individual plots (i)? [o/i] ").strip().lower()
        if choice == "i":
            all_mode = True
        else:
            overlay_mode = True

    if all_mode:
        for f in resolved:
            _do_plot(f, all_flags, auto_technique)
    else:
        _do_overlap(resolved, all_flags, auto_technique)


def _plot_direct(files: list, rest_args: list) -> None:
    _, flags = _parse_flags(rest_args)

    resolved = [_resolve_file(f) for f in files]
    resolved = [f for f in resolved if f]

    if not resolved:
        console.print("[red]File(s) not found.[/red]")
        return

    # Determine technique: from -t flag, auto-detect from filename, or empty
    technique = flags.get("technique") or flags.get("t", "")
    if not technique and resolved:
        from science_cli.core.technique import detect_technique
        technique = detect_technique(Path(resolved[0]).name)

    if len(resolved) == 1:
        _do_plot(resolved[0], flags, technique)
    else:
        _do_overlap(resolved, flags, technique)


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

    elif technique == "ec-eis":
        # EIS: Z' vs -Z'' (Nyquist)
        for candidate in (
            "Z' (Ω)", "Z'", "Re(Z)", "ReZ", "Zre",
            "z'", "z_re", "z_real",
        ):
            if candidate in df.columns:
                xcol = candidate
                break
        for candidate in (
            "-Z'' (Ω)", "-Z''", "Z''", '-Z"',
            "Im(Z)", "ImZ", "Zim", "z''", "z_im", "z_imag",
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

    elif technique == "uv-vis":
        for candidate in ("wavelength", "Wavelength nm.", "Wavelength", "nm"):
            if candidate in df.columns:
                xcol = candidate
                break
        for candidate in ("transmittance", "T%", "T", "Transmittance"):
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
    if technique in ("ec-ca", "ec-cv") and xcol not in (
        "Corrected time (s)", "corrected time",
    ):
        x_numeric = np.asarray(x, dtype=float)
        if np.any(x_numeric > 100):
            x = x_numeric - x_numeric[0]

    mask = ~(np.isnan(x.astype(float)) | np.isnan(y.astype(float)))
    return x[mask], y[mask], xcol, ycol


def _do_plot(filepath: str, flags: dict, technique: str = "") -> None:
    if technique == "ec-eis":
        return _do_eis_plot(filepath, flags)

    from science_cli.core.data_loader import load_data_file

    try:
        load_kwargs = {}
        if technique:
            from science_cli.core.config import get_default_device
            device = get_default_device(technique)
            if device:
                load_kwargs["technique"] = technique
                load_kwargs["device"] = device
        df, info = load_data_file(filepath, **load_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to load file: {e}[/red]")
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply_theme(get_active_theme())
    fig, ax = plt.subplots(figsize=_figsize(flags))

    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, technique)
    if len(x) == 0 or len(y) == 0:
        console.print(
            "[red]Could not determine x/y columns for this technique.[/red]"
        )
        return

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


def _do_eis_plot(filepath: str, flags: dict) -> None:
    """Generate Nyquist, Bode, and optionally circuit-fit-nyquist for an EIS file."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from science_cli.core.data_loader import load_data_file

    try:
        df, info = load_data_file(filepath, technique="ec-eis")
    except Exception as e:
        console.print(f"[red]Failed to load EIS data: {e}[/red]")
        return

    cols = list(df.columns)
    # Resolve column names (try normalized first, fall back to raw)
    def _col(candidates):
        for c in candidates:
            if c in cols:
                return c
        return ""

    freq_col = _col(["frequency", "Frequency (Hz)"])
    z_real_col = _col(["z_real", "Z' (Ω)", "Z'"])
    z_imag_col = _col(["z_imag", "-Z'' (Ω)", "-Z''"])
    mag_col = _col(["magnitude", "Z (Ω)"])
    phase_col = _col(["phase", "-Phase (°)", "Phase (°)"])

    if not freq_col or not z_real_col or not z_imag_col:
        console.print("[red]EIS data missing frequency, Z', or Z'' columns.[/red]")
        return

    freq = df[freq_col].values
    z_real = df[z_real_col].values
    z_imag = df[z_imag_col].values
    mag = df[mag_col].values if mag_col else None
    phase = df[phase_col].values if phase_col else None

    from science_cli.library.electrochem.models import EISData
    from science_cli.plot.eis import plot_eis_bode, plot_eis_fit, plot_eis_nyquist

    apply_theme(get_active_theme())
    stem = Path(filepath).stem
    out_dir = _get_results_dir(filepath)
    dpi = int(flags.get("dpi", 150))

    want_nyquist = not flags.get("bode")
    want_bode = not flags.get("nyquist")
    output_files = []

    # ── Nyquist ──────────────────────────────────────────────────────
    if want_nyquist:
        fig, ax = plot_eis_nyquist(z_real, z_imag, label=stem)
        _apply_figure_kw(ax, flags, stem)
        nyq_name = f"ec-eis-nyquist_{stem}.pdf"
        nyq_path = out_dir / nyq_name
        fig.savefig(nyq_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        console.print(f"[bold green]✓[/bold green] Nyquist saved: {nyq_path}")
        output_files.append(str(nyq_path))

    # ── Bode ──────────────────────────────────────────────────────────
    if want_bode and freq_col and mag_col and phase_col:
        fig, ax1 = plot_eis_bode(freq, mag, phase)
        _apply_figure_kw(ax1, flags, stem)
        bode_name = f"ec-eis-bode_{stem}.pdf"
        bode_path = out_dir / bode_name
        fig.savefig(bode_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        console.print(f"[bold green]✓[/bold green] Bode saved: {bode_path}")
        output_files.append(str(bode_path))

    # ── Circuit fit (--circuit) ──────────────────────────────────────
    circuit_model = flags.get("circuit")
    if circuit_model is not False and circuit_model is not None:
        from science_cli.library.electrochem.eis import best_circuit_fit, circuit_fit

        eis_data = EISData(frequency=freq, impedance=z_real - 1j * z_imag)

        if isinstance(circuit_model, str) and circuit_model not in (True, ""):
            fit = circuit_fit(eis_data, circuit_model)
        else:
            fit = best_circuit_fit(eis_data, candidates=["R_s(C[RW])", "R_s(Q[RW])"])
            circuit_model = fit.get("circuit", "best")

        if "error" not in fit:
            import json

            fz = np.array(fit.get("fit_Z_real", []))
            fzi = np.array(fit.get("fit_Z_imag", []))
            if len(fz) > 0:
                fig, ax = plot_eis_fit(z_real, z_imag, fz, fzi)
                _apply_figure_kw(ax, flags, stem)
                fit_name = f"ec-eis-fit-nyquist_{stem}.pdf"
                fit_path = out_dir / fit_name
                fig.savefig(fit_path, dpi=dpi, bbox_inches="tight")
                plt.close(fig)
                console.print(f"[bold green]✓[/bold green] Fit overlay saved: {fit_path}")
                output_files.append(str(fit_path))

            # Save fit results as JSON
            fit_json = {
                "file": Path(filepath).name,
                "circuit": circuit_model,
                "r_squared": fit.get("r_squared", 0),
                "reduced_chi": fit.get("reduced_chi", 0),
                "nfev": fit.get("nfev", 0),
                "parameters": {
                    n: {"value": v, "stderr": s}
                    for n, v, s in zip(
                        fit.get("parameter_names", []),
                        fit.get("fitted_params", []),
                        fit.get("param_stderr", []),
                    )
                },
            }
            json_name = f"ec-eis-fit-nyquist_{stem}.json"
            json_path = out_dir / json_name
            with open(json_path, "w") as jf:
                json.dump(fit_json, jf, indent=2)
            console.print(f"[bold green]✓[/bold green] Fit results saved: {json_path}")
            output_files.append(str(json_path))

            # Print fit results
            console.print(f"\n  [bold]Circuit fit:[/bold] {circuit_model}  (R²={fit.get('r_squared', 0):.4f})")
            for n, v in zip(fit.get("parameter_names", []), fit.get("fitted_params", [])):
                console.print(f"    {n}: {v:.4e}")
        else:
            console.print(f"  [red]Fit failed: {fit['error']}[/red]")

    # ── KK test (--kk) ──────────────────────────────────────────────
    if flags.get("kk"):
        from science_cli.library.electrochem.eis import kramers_kronig
        eis_data = EISData(frequency=freq, impedance=z_real - 1j * z_imag)
        kk = kramers_kronig(eis_data)
        status = "✓ passed" if kk.get("passes") else "✗ failed"
        console.print(f"\n  [bold]KK test:[/bold] {status}  (score={kk.get('consistency_score', 0):.3f})")

    # ── Manifest ─────────────────────────────────────────────────────
    from science_cli.core.manifest import emit_manifest
    from science_cli.core.project import get_current_project_path
    if output_files:
        emit_manifest(
            output_dir=out_dir,
            command=f"plot {filepath}",
            source_files=[filepath],
            output_files=output_files,
            technique="ec-eis",
            parameters=flags,
            project=get_current_project_path().name if get_current_project_path() else "",
        )


def _do_overlap(files: list, flags: dict, technique: str = "") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

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
            load_kwargs = {}
            if technique:
                from science_cli.core.config import get_default_device
                device = get_default_device(technique)
                if device:
                    load_kwargs["technique"] = technique
                    load_kwargs["device"] = device
            df, info = load_data_file(fp, **load_kwargs)
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
            console.print("[yellow]Usage: --zoom x1,x2 or --zoom x1,x2,y1,y2[/yellow]")
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

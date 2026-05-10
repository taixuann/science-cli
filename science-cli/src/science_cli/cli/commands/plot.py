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
    """Resolve a filename — delegates to core.file_utils.resolve_data_file."""
    from science_cli.core.project import get_current_project_path
    from science_cli.core.file_utils import resolve_data_file
    return resolve_data_file(name, get_current_project_path())


def _detect_technique(filename: str) -> str:
    from science_cli.core.technique import detect_technique
    t = detect_technique(filename)
    return t.lower() if t else ""


def _get_results_dir(filepath: str) -> Path:
    """Determine results directory — delegates to core.file_utils.get_results_dir."""
    from science_cli.core.session import load_session
    from science_cli.core.project import get_current_project_path
    from science_cli.core.file_utils import get_results_dir
    protocol = load_session().get("last_protocol", "")
    proj = get_current_project_path()
    return get_results_dir(filepath, proj, protocol)


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


def _get_active_plot_defaults(technique: str) -> dict:
    """Merge active theme lines defaults with technique template defaults.

    Template values override theme values. Returns a flat dict with keys
    matching CLI flag names (type, linewidth, linestyle, marker, markersize,
    xlabel, ylabel, figsize, format, dpi).
    """
    from science_cli.core.session import get_active_theme
    from science_cli.theme.registry import get_theme, template_to_flags

    defaults: dict[str, str] = {}

    # Layer 1: active theme lines section
    try:
        theme = get_theme(get_active_theme())
        lines = theme.get("lines", {})
        if "linewidth" in lines:
            defaults["linewidth"] = str(lines["linewidth"])
        if "markersize" in lines:
            defaults["markersize"] = str(lines["markersize"])
        if "linestyle" in lines:
            defaults["linestyle"] = str(lines["linestyle"])
        # Figure info for Prompt 2
        figure = theme.get("figure", {})
        figsize = figure.get("figsize", [6.4, 4.8])
        defaults["figsize"] = f"{figsize[0]}x{figsize[1]}" if isinstance(figsize, list) else str(figsize)
        defaults["dpi"] = str(figure.get("dpi", 300))
        savefig = theme.get("savefig", {})
        defaults["format"] = savefig.get("format", "pdf")
    except Exception:
        pass

    # Layer 2: technique template (overrides theme)
    try:
        tmpl = template_to_flags(technique) if technique else {}
    except Exception:
        tmpl = {}
    for key in ("type", "linewidth", "linestyle", "marker", "markersize", "xlabel", "ylabel"):
        if key in tmpl:
            defaults[key] = tmpl[key]

    return defaults


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
    items = [f.name for f in files]
    selected = fzf_select(items, prompt="Select file(s) (Tab to multi-select):", multi=True)
    if not selected:
        return

    # Show selected files summary
    rprint(f"\n[bold]Selected {len(selected)} file(s):[/bold]")
    for f in selected:
        rprint(f"  [dim]• {f}[/dim]")
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

    # Resolve active defaults for display
    active_defaults = _get_active_plot_defaults(auto_technique)

    if auto_technique:
        rprint(f"  [bold]Detected technique:[/bold] {auto_technique}")
        if all_flags:
            rprint(f"  [bold]Pre-filled defaults:[/bold] [dim]{all_flags}[/dim]")

    # --- Column selection menu for generic/unknown techniques ---
    if not auto_technique and selected:
        try:
            from science_cli.core.data_loader import load_data_file
            import questionary
            first_file = _resolve_file(selected[0])
            if first_file:
                df, _info = load_data_file(first_file)
                columns = [c for c in df.columns.tolist() if c and df[c].dtype != "object"]
                if len(columns) >= 2:
                    rprint("\n  [bold]Column selection[/bold] (unknown technique — pick columns manually)\n")
                    xcol = questionary.select(
                        "Select X column:",
                        choices=columns,
                        default=columns[0],
                    ).ask()
                    ycol = questionary.select(
                        "Select Y column:",
                        choices=columns,
                        default=columns[1] if len(columns) > 1 else columns[0],
                    ).ask()
                    group_choices = [questionary.Choice(title=c, value=c) for c in columns]
                    group_choices.append(questionary.Choice(title="(none)", value=""))
                    groupcol = questionary.select(
                        "Select category/group column (optional):",
                        choices=group_choices,
                        default="",
                    ).ask()
                    if xcol:
                        all_flags["xcol"] = xcol
                    if ycol:
                        all_flags["ycol"] = ycol
                    if groupcol:
                        all_flags["groupcol"] = groupcol
        except Exception as e:
            rprint(f"  [dim](column detection skipped: {e})[/dim]")

    # Prompt 1: Style / analysis flags
    style_hint = _technique_hints(auto_technique).get(
        "plot_style",
        "--type line|scatter | --color | --linewidth | --linestyle | --marker | --markersize",
    )
    rprint(f"  [dim]# {style_hint}[/dim]")

    # Format active style defaults for display
    style_parts = []
    for key in ("type", "linewidth", "linestyle", "marker", "markersize"):
        val = active_defaults.get(key)
        if val is not None:
            style_parts.append(f"--{key} {val}")
    if style_parts:
        rprint(f"  [dim]  Active: {'  '.join(style_parts)}[/dim]")

    raw_style = input("  Style / analysis options (Enter to keep defaults): ").strip()
    if raw_style:
        _, style_flags = _parse_flags(raw_style.split())
        all_flags.update(style_flags)

    # Prompt 2: Figure / output flags
    fig_hint = _technique_hints(auto_technique).get(
        "figure",
        "-n name.pdf|png|svg | --label-name n1,n2,... | --title | --xlabel | --ylabel | --xlim | --ylim | --zoom x1,x2,y1,y2 | --size | --dpi | --grid | --legend",
    )
    rprint(f"  [dim]# {fig_hint}[/dim]")

    # Format active figure defaults for display
    fig_parts = []
    figsize = active_defaults.get("figsize")
    if figsize:
        fig_parts.append(f"--size {figsize}")
    fig_fmt = active_defaults.get("format")
    if fig_fmt:
        fig_parts.append(f"--format {fig_fmt}")
    dpi = active_defaults.get("dpi")
    if dpi:
        fig_parts.append(f"--dpi {dpi}")
    xlabel = active_defaults.get("xlabel")
    if xlabel:
        fig_parts.append(f"--xlabel '{xlabel}'")
    ylabel = active_defaults.get("ylabel")
    if ylabel:
        fig_parts.append(f"--ylabel '{ylabel}'")
    if fig_parts:
        rprint(f"  [dim]  Active: {'  '.join(fig_parts)}[/dim]")

    raw_figure = input("  Figure options (Enter to keep defaults): ").strip()
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
    df: "pd.DataFrame", info: dict, technique: str = "", flags: dict | None = None
) -> tuple:
    """Return (x, y, xlabel, ylabel) using registry ColumnMap or fallback heuristics.

    Priority: --xcol/--ycol flags → registry ColumnMap → hardcoded per-technique aliases → first two numeric columns.
    """
    import numpy as np

    xcol, ycol = "", ""
    xlabel, ylabel = "", ""

    # 0. User-specified --xcol / --ycol take highest priority
    if flags:
        if flags.get("xcol") and flags["xcol"] in df.columns:
            xcol = flags["xcol"]
        if flags.get("ycol") and flags["ycol"] in df.columns:
            ycol = flags["ycol"]

    # 1. Try extension registry ColumnMap (preferred path)
    if technique and (not xcol or not ycol):
        try:
            from science_cli.extensions import get_registry
            registry = get_registry()
            cm = registry.column_maps.get(technique)
            if cm is not None:
                xcol, ycol, xlabel, ylabel, _extras = cm.resolve(list(df.columns))
        except ImportError:
            pass

    # 2. Fallback: hardcoded per-technique aliases (for when no registry entry)
    if not xcol or not ycol:
        if technique == "ec-ca":
            for candidate in (
                "Corrected time (s)", "corrected time", "time",
                "Time", "Time (s)", "t/s",
            ):
                if candidate in df.columns:
                    xcol = candidate; break
            for candidate in (
                "WE(1).Current (A)", "Current (A)", "current",
                "I", "I/A", "<I>/A",
            ):
                if candidate in df.columns:
                    ycol = candidate; break
        elif technique == "ec-cv":
            for candidate in (
                "WE(1).Potential (V)", "Potential (V)", "potential",
                "Potential applied (V)", "E", "E/V", "V",
            ):
                if candidate in df.columns:
                    xcol = candidate; break
            for candidate in (
                "WE(1).Current (A)", "Current (A)", "current",
                "I", "I/A",
            ):
                if candidate in df.columns:
                    ycol = candidate; break
        elif technique == "ec-eis":
            for candidate in (
                "Z' (Ω)", "Z'", "Re(Z)", "ReZ", "Zre", "Z_real",
                "z'", "z_re",
            ):
                if candidate in df.columns:
                    xcol = candidate; break
            for candidate in (
                "-Z'' (Ω)", "-Z''", "Z''", 'Z"', "-Z\"",
                "Im(Z)", "ImZ", "Zim", "Z_imag", "z''", "z_im",
            ):
                if candidate in df.columns:
                    ycol = candidate; break
        elif technique in ("iv-sweep", "iv-breakdown", "iv-leakage"):
            for candidate in (
                "Voltage (V)", "voltage", "V",
                "WE(1).Potential (V)", "Potential (V)",
                "BV", "Bias Voltage (V)", "bias_voltage",
            ):
                if candidate in df.columns:
                    xcol = candidate; break
            for candidate in (
                "Current (A)", "current", "I", "I/A",
                "WE(1).Current (A)",
                "Bi", "Bias Current (A)", "bias_current",
            ):
                if candidate in df.columns:
                    ycol = candidate; break
        elif technique in ("mem-endurance", "mem-retention", "mem-switching"):
            numeric = [
                c for c in df.select_dtypes(include=[np.number]).columns
                if c not in ("Index", "index")
            ]
            if len(numeric) >= 2:
                xcol, ycol = numeric[0], numeric[1]

    # 3. Universal fallback: first two numeric columns
    if not xcol or not ycol:
        numeric = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c not in ("Index", "index")
        ]
        if len(numeric) >= 2:
            xcol, ycol = numeric[0], numeric[1]
        else:
            return np.array([]), np.array([]), "", ""

    if not xlabel:
        xlabel = xcol
    if not ylabel:
        ylabel = ycol

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
    return x[mask], y[mask], xlabel, ylabel


def _do_plot(filepath: str, flags: dict, technique: str = "") -> None:
    from science_cli.core.data_loader import load_data_file
    from science_cli.plot import setup_backend, create_figure, parse_figsize
    import matplotlib.pyplot as plt
    import numpy as np

    try:
        df, info = load_data_file(filepath)
    except Exception as e:
        console.print(f"[red]Failed to load file: {e}[/red]")
        return

    # Apply extension plot presets from registry (user flags override)
    if technique:
        try:
            from science_cli.extensions import get_registry
            registry = get_registry()
            preset = registry.plot_presets.get(technique, {})
            # Apply preset defaults only for keys not set by user
            for key, val in preset.items():
                if key not in flags:
                    flags[key] = val
        except ImportError:
            pass

    setup_backend(interactive=False)

    x, y, xlabel, ylabel = _resolve_xy_columns(df, info, technique, flags)
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

    # --- EIS dispatch: use dedicated Nyquist/Bode/fit plotting ---
    if technique == "ec-eis":
        _plot_eis(df, filepath, x, y, xlabel, ylabel, flags)
        return

    # --- Generic plot (non-EIS techniques) ---
    fig, ax = create_figure(theme=get_active_theme(), figsize=parse_figsize(flags))

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

    # Optional: run extension analyzer and display results
    if technique:
        try:
            from science_cli.extensions import get_registry
            registry = get_registry()
            analyzer = registry.analyzers.get(technique)
            if analyzer is not None:
                _run_analyzer_and_report(analyzer, df, technique, registry, flags)
        except ImportError:
            pass

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


def _plot_eis(
    df: "pd.DataFrame", filepath: str,
    x: "np.ndarray", y: "np.ndarray",
    xlabel: str, ylabel: str, flags: dict,
) -> None:
    """EIS-specific plot dispatch: Nyquist, Bode, circuit fit, K-K check."""
    import numpy as np
    import matplotlib.pyplot as plt
    from pathlib import Path

    from science_cli.core.session import get_active_theme
    from science_cli.plot import create_figure, parse_figsize, apply_figure_kw
    from science_cli.plot.eis import plot_eis_nyquist, plot_eis_bode, plot_eis_fit
    from science_cli.extensions import get_registry

    # Resolve extras (frequency, magnitude, phase) from registry ColumnMap
    registry = get_registry()
    cm = registry.column_maps.get("ec-eis")
    extras: dict[str, str] = {}
    if cm is not None:
        _, _, _, _, extras = cm.resolve(list(df.columns))

    # Frequency column
    f_col = extras.get("frequency", "")
    if f_col and f_col in df.columns:
        freq = df[f_col].values.astype(float)
    else:
        freq = np.arange(len(x), dtype=float)

    # Magnitude column
    mag_col = extras.get("magnitude", "")
    if mag_col and mag_col in df.columns:
        z_mag = df[mag_col].values.astype(float)
    else:
        z_mag = np.sqrt(x.astype(float) ** 2 + y.astype(float) ** 2)

    # Phase column
    phase_col = extras.get("phase", "")
    if phase_col and phase_col in df.columns:
        z_phase = df[phase_col].values.astype(float)
    else:
        z_phase = np.angle(x.astype(float) - 1j * y.astype(float), deg=True)

    stem = Path(filepath).stem
    out_dir = _get_results_dir(filepath)
    theme = get_active_theme()

    has_eis_flag = any(k in flags for k in ("nyquist", "bode", "circuit", "kk"))
    dpi = int(flags.get("dpi", 150))

    if flags.get("circuit"):
        # --- Circuit fit + Nyquist overlay ---
        circuit_model = flags.get("circuit", "RRC")
        bare_circuit = circuit_model is True  # True only for bare --circuit (no arg)
        if circuit_model is True:
            circuit_model = "RRC"
        circuit_model = str(circuit_model)
        _do_eis_fit_and_plot(
            df, filepath, x, y, freq, circuit_model, flags,
            stem, out_dir, theme, dpi,
            bare_circuit=bare_circuit,
        )

    elif flags.get("kk"):
        # --- Kramers-Kronig check ---
        _do_eis_kk(df, x, y, freq, flags, stem)

    elif flags.get("nyquist"):
        # --- Nyquist only ---
        fig, ax = plot_eis_nyquist(
            z_real=x.astype(float),
            z_imag=y.astype(float),  # y is ImZ (raw Z'') — plot_eis_nyquist negates internally
            flags=flags, label=stem,
        )
        _apply_figure_kw(ax, flags, stem)
        nyq_name = flags.get("n") or flags.get("name", f"{stem}_nyquist.pdf")
        if not Path(nyq_name).suffix:
            nyq_name = str(Path(nyq_name)) + ".pdf"
        save_path = out_dir / nyq_name
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        console.print(f"[bold green]✓[/bold green] Nyquist saved: {save_path}")
        _emit_eis_manifest(out_dir, filepath, flags, [str(save_path)], "ec-eis")

    elif flags.get("bode"):
        # --- Bode only ---
        fig, axes = plot_eis_bode(freq, z_mag, z_phase, flags=flags)
        bode_name = flags.get("n") or flags.get("name", f"{stem}_bode.pdf")
        if not Path(bode_name).suffix:
            bode_name = str(Path(bode_name)) + ".pdf"
        save_path = out_dir / bode_name
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        console.print(f"[bold green]✓[/bold green] Bode saved: {save_path}")
        _emit_eis_manifest(out_dir, filepath, flags, [str(save_path)], "ec-eis")

    else:
        # --- Default: both Nyquist + Bode ---
        # Nyquist
        fig1, ax1 = plot_eis_nyquist(
            z_real=x.astype(float),
            z_imag=y.astype(float),  # y is ImZ (raw Z'') — plot_eis_nyquist negates internally
            flags=flags, label=stem,
        )
        _apply_figure_kw(ax1, flags, stem)
        nyq_name = f"{stem}_nyquist.pdf"
        if flags.get("n") or flags.get("name"):
            nyq_name = flags.get("n") or flags.get("name", nyq_name)
        if not Path(nyq_name).suffix:
            nyq_name = str(Path(nyq_name)) + ".pdf"
        save_nyq = out_dir / nyq_name
        fig1.savefig(save_nyq, dpi=dpi, bbox_inches="tight")
        plt.close(fig1)

        # Bode
        fig2, axes2 = plot_eis_bode(freq, z_mag, z_phase, flags=flags)
        bode_name = f"{stem}_bode.pdf"
        if flags.get("n") or flags.get("name"):
            bode_name = flags.get("n") or flags.get("name", bode_name)
        if not Path(bode_name).suffix:
            bode_name = str(Path(bode_name)) + ".pdf"
        save_bode = out_dir / bode_name
        fig2.savefig(save_bode, dpi=dpi, bbox_inches="tight")
        plt.close(fig2)

        console.print(
            f"[bold green]✓[/bold green] Generated Nyquist + Bode plots:"
        )
        console.print(f"    [dim]Nyquist: {save_nyq}[/dim]")
        console.print(f"    [dim]Bode: {save_bode}[/dim]")
        _emit_eis_manifest(
            out_dir, filepath, flags, [str(save_nyq), str(save_bode)], "ec-eis",
        )


def _py_eis_fit(
    freq: "np.ndarray",
    Z_data: "np.ndarray",
    circuit_model: str,
) -> dict:
    """Fit EIS data using PyEIS circuit models + lmfit.

    Returns dict with keys: success, parameter_names, fitted_params, param_stderr,
    r_squared, reduced_chi, fit_Z_real, fit_Z_imag, circuit_model.
    """
    import numpy as np
    import PyEIS

    try:
        from lmfit import Minimizer, Parameters
    except ImportError:
        return {"error": "lmfit not installed — run: pip install lmfit"}

    f = np.asarray(freq, dtype=float)
    Z = np.asarray(Z_data, dtype=complex)
    Z_real = np.real(Z)
    Z_imag = np.imag(Z)

    # --- Circuit model registry ---
    # Each entry: (sim_function, param_spec_dict, unit_map)
    # param_spec: {name: (initial, min, max, vary)}
    # sim_function(freq, **params) -> complex impedance array

    def _z_randles(f, Rs, Rct, Cdl):
        """Simple Randles: Rs + (Rct || Cdl)."""
        w = 2 * np.pi * f
        return Rs + 1.0 / (1.0 / Rct + 1j * w * Cdl)

    def _z_rc(f, R, C):
        """Series RC."""
        return PyEIS.cir_RC(f, C=C, R=R)

    def _z_rsrcq(f, Rs, R1, C1, Q, n):
        """Rs + (R1||C1) + Q."""
        return PyEIS.cir_RsRCQ(f, Rs, R1, C1, Q, n)

    def _z_rsrqq(f, Rs, R1, Q1, n1, Q2, n2):
        """Rs + Q1 + (R1||Q2)."""
        return PyEIS.cir_RsRQQ(f, Rs=Rs, R1=R1, Q=Q1, n=n1, Q1=Q2, n1=n2)

    # Estimate initial guesses from data
    rs_guess = max(np.real(Z[-1]), 1.0) if len(Z) > 0 else 100.0
    rct_guess = max(np.real(Z[0]) - np.real(Z[-1]), 10.0) if len(Z) > 1 else 1000.0
    # Find frequency near the peak of -Z'' for time constant estimate
    neg_z_imag = -Z_imag
    peak_idx = int(np.argmax(neg_z_imag)) if len(neg_z_imag) > 0 else len(f) // 2
    f_peak = f[min(peak_idx, len(f) - 1)] if len(f) > 0 else 1.0
    c_guess = max(1.0 / (2 * np.pi * f_peak * rct_guess), 1e-12) if rct_guess > 0 else 1e-6

    circuits = {
        "RRC": {
            "sim": _z_randles,
            "params": {
                "Rs": (rs_guess, 0, 1e9, True),
                "Rct": (rct_guess, 0, 1e12, True),
                "Cdl": (c_guess, 1e-15, 1.0, True),
            },
            "units": {"Rs": "Ω", "Rct": "Ω", "Cdl": "F"},
        },
        "RC": {
            "sim": _z_rc,
            "params": {
                "R": (rs_guess + rct_guess, 0, 1e12, True),
                "C": (c_guess, 1e-15, 1.0, True),
            },
            "units": {"R": "Ω", "C": "F"},
        },
        "RQR": {
            "sim": lambda f, Rs, R, Q, n: PyEIS.cir_RsRQ(f, Rs=Rs, R=R, Q=Q, n=n),
            "params": {
                "Rs": (rs_guess, 0, 1e9, True),
                "R": (rct_guess, 0, 1e12, True),
                "Q": (c_guess, 1e-12, 1.0, True),
                "n": (0.9, 0.5, 1.0, True),
            },
            "units": {"Rs": "Ω", "R": "Ω", "Q": "S·s^n", "n": ""},
        },
        "RsRCQ": {
            "sim": _z_rsrcq,
            "params": {
                "Rs": (rs_guess, 0, 1e9, True),
                "R1": (rct_guess, 0, 1e12, True),
                "C1": (c_guess, 1e-15, 1.0, True),
                "Q": (c_guess * 0.01, 1e-15, 1.0, True),
                "n": (0.9, 0.5, 1.0, True),
            },
            "units": {"Rs": "Ω", "R1": "Ω", "C1": "F", "Q": "S·s^n", "n": ""},
        },
        "RsRQQ": {
            "sim": _z_rsrqq,
            "params": {
                "Rs": (rs_guess, 0, 1e9, True),
                "R1": (rct_guess, 0, 1e12, True),
                "Q1": (c_guess, 1e-12, 1.0, True),
                "n1": (0.9, 0.5, 1.0, True),
                "Q2": (c_guess * 0.1, 1e-12, 1.0, True),
                "n2": (0.9, 0.5, 1.0, True),
            },
            "units": {"Rs": "Ω", "R1": "Ω", "Q1": "S·s^n", "n1": "", "Q2": "S·s^n", "n2": ""},
        },
    }

    if circuit_model not in circuits:
        return {"error": f"Unknown circuit model: {circuit_model}. Available: {list(circuits.keys())}"}

    circ = circuits[circuit_model]

    # Build lmfit Parameters
    params = Parameters()
    for name, (init, lo, hi, vary) in circ["params"].items():
        params.add(name, value=init, min=lo, max=hi, vary=vary)

    # Normalize residual: use log-space weighting to balance real and imaginary
    def residual(pars, f_arr, Z_meas):
        """Weighted residual: (Z_model - Z_meas) / |Z_meas|."""
        vals = pars.valuesdict()
        Z_model = circ["sim"](f_arr, **vals)
        weight = np.abs(Z_meas)
        weight = np.maximum(weight, np.median(weight) * 0.1)  # floor to avoid div by 0
        res_real = (np.real(Z_model) - np.real(Z_meas)) / weight
        res_imag = (np.imag(Z_model) - np.imag(Z_meas)) / weight
        return np.concatenate([res_real, res_imag])

    minimizer = Minimizer(residual, params, fcn_args=(f, Z))
    result = minimizer.minimize(method="leastsq")

    # Compute fit quality metrics
    n_data = 2 * len(Z)  # real + imag
    n_params = len([p for p in result.params.values() if p.vary])
    dof = max(n_data - n_params, 1)
    red_chi = result.redchi if hasattr(result, "redchi") and result.redchi else np.sum(result.residual**2) / dof

    # R-squared on the raw (unweighted) residual
    Z_fit = circ["sim"](f, **result.params.valuesdict())
    ss_res = np.sum((np.real(Z_fit - Z))**2 + (np.imag(Z_fit - Z))**2)
    ss_tot = np.sum((np.real(Z - np.mean(Z)))**2 + (np.imag(Z - np.mean(Z)))**2)
    r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    if not result.success:
        return {"error": f"Fit did not converge: {result.message}"}

    # Extract fitted parameters and stderr
    param_names = []
    fitted_params = []
    param_stderr = []
    for name in circ["params"]:
        p = result.params.get(name)
        if p is not None:
            param_names.append(name)
            fitted_params.append(p.value)
            param_stderr.append(p.stderr if p.stderr is not None else 0.0)

    return {
        "success": True,
        "circuit_model": circuit_model,
        "parameter_names": param_names,
        "fitted_params": fitted_params,
        "param_stderr": param_stderr,
        "r_squared": r_sq,
        "reduced_chi": red_chi,
        "fit_Z_real": np.real(Z_fit).tolist(),
        "fit_Z_imag": np.imag(Z_fit).tolist(),
        "units": circ["units"],
    }


def _do_eis_fit_and_plot(
    df: "pd.DataFrame", filepath: str,
    x: "np.ndarray", y: "np.ndarray",
    freq: "np.ndarray", circuit_model: str,
    flags: dict, stem: str, out_dir: "Path",
    theme: str, dpi: int,
    bare_circuit: bool = False,
) -> None:
    """Run circuit fit (custom lmfit models), plot Nyquist + fit overlay, save CSV + manifest.

    When bare_circuit=True (bare --circuit flag with no model name), auto-fits all
    registered circuit models and picks the one with highest R².
    """
    import numpy as np
    import matplotlib.pyplot as plt
    import csv
    from pathlib import Path

    from science_cli.plot.eis import plot_eis_fit
    from science_cli.plot import apply_figure_kw
    from science_cli.plot.eis_circuits import CIRCUIT_REGISTRY, fit_eis_circuit

    # Build complex impedance: x = Z', y = ImZ (raw Z'')
    z_real = x.astype(float)
    z_imag = y.astype(float)  # raw Z'' — plot_eis_fit negates internally
    Z = z_real + 1j * z_imag

    # --- Auto-best: try all models when bare --circuit ---
    if bare_circuit:
        rprint("  [dim]Auto-fitting all circuit models...[/dim]")
        best_fit = None
        best_r2 = -np.inf
        for name in CIRCUIT_REGISTRY:
            trial = fit_eis_circuit(freq, Z, name)
            if "error" in trial:
                rprint(f"    [dim]{name:6s}: [red]failed[/red] — {trial['error']}[/dim]")
                continue
            r2 = trial["r_squared"]
            marker = ""
            if r2 > best_r2:
                best_r2 = r2
                best_fit = trial
                marker = " ← best"
            rprint(f"    [dim]{name:6s}: R²={r2:.4f}{marker}[/dim]")

        if best_fit is None:
            console.print("[red]All circuit models failed to fit.[/red]")
            return
        fit = best_fit
        circuit_model = fit["circuit"]
        rprint(f"  [bold green]Winner: {circuit_model}[/bold green]  R²={best_r2:.4f}")
    else:
        rprint(f"  [dim]Fitting circuit model: {circuit_model} ...[/dim]")
        fit = fit_eis_circuit(freq, Z, circuit_model)
        if "error" in fit:
            console.print(f"[red]Circuit fit failed: {fit['error']}[/red]")
            return

    # --- Report fit results with % errors ---
    rprint(f"  Circuit: {fit['circuit']}  R²={fit['r_squared']:.4f}  red. χ²={fit['reduced_chi']:.2e}")
    for name, val, err, pct in zip(
        fit["parameter_names"], fit["fitted_params"],
        fit["param_stderr"], fit["param_error_pct"],
    ):
        pct_str = f"{pct:.1f}%" if pct is not None else "  N/A  "
        rprint(f"    {name:6s} {val:>11.3e}  ± {pct_str:>6s}  (stderr: {err:.3e})")

    # --- Save fit parameters as CSV (with error_pct column) ---
    csv_path = out_dir / f"{stem}_fit_results.csv"
    units = fit.get("units", {})
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["parameter", "value", "stderr", "error_pct", "unit"])
        for i, name in enumerate(fit["parameter_names"]):
            val = fit["fitted_params"][i] if i < len(fit["fitted_params"]) else None
            err = fit["param_stderr"][i] if i < len(fit["param_stderr"]) else None
            pct = fit["param_error_pct"][i] if i < len(fit["param_error_pct"]) else None
            unit = units.get(name, "")
            writer.writerow([
                name,
                f"{val:.6e}" if val is not None else "",
                f"{err:.6e}" if err else "",
                f"{pct:.2f}" if pct is not None else "N/A",
                unit,
            ])
        # Quality metrics
        writer.writerow([])
        writer.writerow(["# Fit quality"])
        writer.writerow(["r_squared", f"{fit['r_squared']:.6f}", "", "", ""])
        writer.writerow(["reduced_chi_squared", f"{fit['reduced_chi']:.6f}", "", "", ""])

    console.print(f"[bold green]✓[/bold green] Fit results saved: {csv_path}")

    # --- Plot Nyquist with fit overlay ---
    fit_real = np.array(fit["fit_Z_real"])
    fit_imag = np.array(fit["fit_Z_imag"])
    if len(fit_real) == 0:
        console.print("[yellow]No fitted impedance data to plot.[/yellow]")
        return

    fig, ax = plot_eis_fit(
        z_real=z_real,
        z_imag=z_imag,  # raw Z'' — plot_eis_fit negates internally
        fit_real=fit_real,
        fit_imag=fit_imag,
        flags=flags,
    )
    ax.set_title(f"{stem} — {circuit_model} fit")
    _apply_figure_kw(ax, flags, stem)

    nyq_name = flags.get("n") or flags.get("name", f"{stem}_circuit_fit.pdf")
    if not Path(nyq_name).suffix:
        nyq_name = str(Path(nyq_name)) + ".pdf"
    save_path = out_dir / nyq_name
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] Fit overlay saved: {save_path}")

    # --- Build fit results dict for manifest (includes error_pct) ---
    fit_params_dict = {}
    for i, name in enumerate(fit["parameter_names"]):
        val = fit["fitted_params"][i] if i < len(fit["fitted_params"]) else None
        err = fit["param_stderr"][i] if i < len(fit["param_stderr"]) else None
        pct = fit["param_error_pct"][i] if i < len(fit["param_error_pct"]) else None
        fit_params_dict[name] = {"value": val, "stderr": err, "error_pct": pct}

    fit_results = {
        "circuit_fit": {
            "model": circuit_model,
            "parameters": fit_params_dict,
            "quality": {
                "r_squared": fit["r_squared"],
                "reduced_chi": fit["reduced_chi"],
            },
            "csv_file": csv_path.name,
        },
    }
    _emit_eis_manifest(
        out_dir, filepath, flags, [str(save_path), str(csv_path)], "ec-eis",
        results=fit_results,
    )


def _do_eis_kk(
    df: "pd.DataFrame", x: "np.ndarray", y: "np.ndarray",
    freq: "np.ndarray", flags: dict, stem: str,
) -> None:
    """Run Kramers-Kronig validation and report results."""
    import numpy as np
    from science_electrochem.models import EISData
    from science_electrochem.eis import analyze_eis

    z_real = x.astype(float)
    z_imag = -y.astype(float)  # convert -Z'' to raw Z''
    Z = z_real + 1j * z_imag
    data = EISData(frequency=freq, impedance=Z)

    rprint(f"  [dim]Running Kramers-Kronig validation ...[/dim]")
    options = {"circuit_model": "RRC", "kk": True}
    result = analyze_eis(data, options)
    _report_eis_result(result)


def _emit_eis_manifest(
    out_dir: "Path", filepath: str, flags: dict,
    output_files: list[str], technique: str,
    results: dict | None = None,
) -> None:
    """Emit manifest.json for EIS plot operations."""
    from pathlib import Path
    from science_cli.core.manifest import emit_manifest
    from science_cli.core.project import get_current_project_path

    emit_manifest(
        output_dir=out_dir,
        command=f"plot {filepath}",
        source_files=[filepath],
        output_files=output_files,
        technique=technique,
        parameters=flags,
        results=results or {},
        project=get_current_project_path().name if get_current_project_path() else "",
    )


def _run_analyzer_and_report(
    analyzer, df: "pd.DataFrame", technique: str, registry, flags: dict | None = None
) -> None:
    """Run an extension analyzer and display results on console.

    Handles the fact that analyzer function signatures vary across extensions
    (some expect domain model objects, others expect raw arrays).
    Uses the registry ColumnMap to identify columns for model construction.
    """
    import numpy as np

    # Resolve columns via ColumnMap
    xcol, ycol, xlabel, ylabel, extras = "", "", "", "", {}
    cm = registry.column_maps.get(technique)
    if cm is not None:
        xcol, ycol, xlabel, ylabel, extras = cm.resolve(list(df.columns))

    # Fallback: use first two numeric columns
    if not xcol or not ycol:
        numeric = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c not in ("Index", "index")
        ]
        if len(numeric) >= 2:
            xcol, ycol = numeric[0], numeric[1]

    if not xcol or not ycol:
        return  # Cannot run analysis without columns

    x = np.asarray(df[xcol].values, dtype=float)
    y = np.asarray(df[ycol].values, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    try:
        # Dispatch based on technique family to handle model construction
        if technique.startswith("ec-"):
            _run_electrochem_analyzer(analyzer, technique, x, y, df, extras, flags)
        elif technique.startswith("iv-"):
            _run_iv_analyzer(analyzer, technique, x, y)
        elif technique.startswith("mem-"):
            _run_memristor_analyzer(analyzer, technique, x, y, df)
        else:
            # Generic: try calling with raw arrays and hope for the best
            result = analyzer(x, y)
            if result and isinstance(result, dict):
                rprint(f"  [dim]Analysis: {result}[/dim]")
    except Exception:
        pass  # Analysis is best-effort in plot mode


def _run_electrochem_analyzer(
    analyzer, technique: str, x: "np.ndarray", y: "np.ndarray",
    df: "pd.DataFrame", extras: dict, flags: dict | None = None
) -> None:
    """Run electrochem analyzers (CV, CA, EIS) with model construction."""
    flags = flags or {}
    # Lazy imports — extension models live in extension packages
    if technique == "ec-cv":
        from science_electrochem.models import CVData
        data = CVData(potential=x, current=y, scan_rate=0.0)
        result = analyzer(data, {})
        _report_cv_result(result)
    elif technique == "ec-ca":
        from science_electrochem.models import CAData
        data = CAData(time=x, current=y)
        result = analyzer(data, {})
        _report_ca_result(result)
    elif technique == "ec-eis":
        import numpy as np
        import pandas as pd
        from science_electrochem.models import EISData
        # EIS needs frequency, Z' and Z'' (complex impedance)
        z_col = extras.get("z_imag", extras.get("z_real", ""))
        f_col = extras.get("frequency", "")
        z_real = x
        z_imag = np.zeros_like(x)
        if z_col and z_col in df.columns:
            z_imag = np.asarray(df[z_col].values, dtype=float)
        freq = np.arange(len(x), dtype=float)
        if f_col and f_col in df.columns:
            freq = np.asarray(df[f_col].values, dtype=float)
        mask = ~(np.isnan(z_real) | np.isnan(z_imag) | np.isnan(freq))
        z = z_real[mask] + 1j * z_imag[mask]
        data = EISData(frequency=freq[mask], impedance=z)
        circuit_model = flags.get("circuit", "RRC")
        if circuit_model is True:
            circuit_model = "RRC"
        options = {
            "circuit_model": circuit_model,
            "kk": flags.get("kk", False),
        }
        result = analyzer(data, options)
        _report_eis_result(result)


def _run_iv_analyzer(
    analyzer, technique: str, x: "np.ndarray", y: "np.ndarray"
) -> None:
    """Run IV analyzers (extract_resistance, extract_breakdown_voltage)."""
    result = analyzer(x, y)
    if result and isinstance(result, dict):
        if "resistance" in result and result["resistance"] is not None:
            rprint(f"  Resistance: {result['resistance']:.2e} Ω  (R²={result.get('r_squared', 0):.4f})")
        if "breakdown_voltage" in result and result["breakdown_voltage"] is not None:
            rprint(f"  V_bd: {result['breakdown_voltage']:.4f} V  @ {result['breakdown_current']:.2e} A")


def _run_memristor_analyzer(
    analyzer, technique: str, x: "np.ndarray", y: "np.ndarray",
    df: "pd.DataFrame"
) -> None:
    """Run memristor analyzers — pass DataFrame for flexibility."""
    try:
        result = analyzer(df)
        if result and isinstance(result, dict):
            rprint(f"  [dim]{technique} analysis: {list(result.keys())}[/dim]")
    except Exception:
        pass


def _report_cv_result(result: dict) -> None:
    peaks = result.get("peaks", {})
    if peaks:
        na = peaks.get("n_anodic", 0)
        nc = peaks.get("n_cathodic", 0)
        rprint(f"  CV peaks: {na} anodic, {nc} cathodic")
        for pk in peaks.get("anodic_peaks", []):
            rprint(f"    E_pa={pk.get('potential', 0):.4f}V  I_pa={pk.get('current', 0):.4e}A")
        for pk in peaks.get("cathodic_peaks", []):
            rprint(f"    E_pc={pk.get('potential', 0):.4f}V  I_pc={pk.get('current', 0):.4e}A")
        if "average_peak_separation" in peaks:
            rprint(f"    ΔE_p = {peaks['average_peak_separation']:.4f}V")


def _report_ca_result(result: dict) -> None:
    cr = result.get("cottrell", {})
    if cr and "error" not in cr:
        rprint(f"  Cottrell slope: {cr.get('slope', 0):.4e} A·√s  R²={cr.get('r_squared', 0):.4f}")
    ss = result.get("steady_state", {})
    if ss:
        rprint(f"  Steady state: {ss.get('steady_state_current', 0):.4e}A")


def _report_eis_result(result: dict) -> None:
    fit = result.get("circuit_fit", {})
    if fit and "error" not in fit:
        rprint(f"  Circuit: {fit.get('circuit', '?')}  R²={fit.get('r_squared', 0):.4f}")
        for n, v in zip(fit.get("parameter_names", []), fit.get("fitted_params", [])):
            rprint(f"    {n}: {v:.4e}")
    kk = result.get("kk", {})
    if kk:
        status = "✓ passed" if kk.get("passes") else "✗ failed"
        rprint(f"  KK test: {status}  (score={kk.get('consistency_score', 0):.3f})")


def _do_overlap(files: list, flags: dict, technique: str = "") -> None:
    """Plot multiple files overlaid on the same axes."""
    import numpy as np
    import matplotlib.pyplot as plt
    from science_cli.core.data_loader import load_data_file
    from science_cli.plot import setup_backend, create_figure, parse_figsize

    setup_backend(interactive=False)
    fig, ax = create_figure(theme=get_active_theme(), figsize=parse_figsize(flags))
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
            xi, yi, _, _ = _resolve_xy_columns(df, info, technique, flags)
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


def _apply_figure_kw(ax, flags: dict, title_default: str) -> None:
    """Apply figure styling — delegates to plot engine, then handles --zoom separately."""
    from science_cli.plot import apply_figure_kw
    apply_figure_kw(ax, flags, title_default)
    if flags.get("zoom"):
        _apply_zoom(ax, flags["zoom"])
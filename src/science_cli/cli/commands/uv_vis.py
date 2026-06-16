"""uv_vis command handler — specialized UV-Vis spectroscopy plotting and analysis with FZF integration."""

from pathlib import Path
import re
import numpy as np
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag
from science_cli.core.data_loader import load_data_file

console = Console()


def _parse_flags(args: list) -> tuple:
    from science_cli.cli.commands.plot import _parse_flags as plot_parse
    return plot_parse(args)


def _resolve_file(name: str) -> str:
    from science_cli.cli.commands.plot import _resolve_file as plot_resolve
    return plot_resolve(name)


def _get_project_raw_dir() -> Path:
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if proj:
        raw_dir = proj / "data" / "raw"
        if raw_dir.exists():
            return raw_dir
    return Path()


def _get_uv_files(raw_dir: Path) -> list[Path]:
    from science_cli.core.technique import detect_technique
    return sorted(
        f for f in raw_dir.iterdir()
        if f.is_file()
        and (detect_technique(f.name) == "uv-vis" or any(p in f.name.lower() for p in ["_uv", "_uv-vis", "uvvis"]))
    )


def _get_results_dir(filepath: str) -> Path:
    import yaml
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


def _uv_fzf_pick_multi(prompt: str = "Select UV-Vis file(s)") -> list[str]:
    raw_dir = _get_project_raw_dir()
    if not raw_dir:
        console.print("[yellow]No project open.[/yellow]")
        return []

    files = _get_uv_files(raw_dir)
    if not files:
        console.print("[yellow]No UV-Vis files found.[/yellow]")
        return []

    from science_cli.core.fzf_utils import fzf_select

    # Build file-to-step mapping from all protocols
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    paths = ProjectPaths(proj)
    file_step_map: dict[str, tuple[str, str, str]] = {}
    for py in paths.list_protocol_yamls():
        pname = py.stem
        with open(py) as f:
            proto_data = __import__("yaml").safe_load(f) or {}
        for s in proto_data.get("steps", []):
            tech = s.get("technique", "").lower()
            for entry in s.get("files", []):
                fname = entry["file"] if isinstance(entry, dict) else entry
                file_step_map[fname] = (pname, s["name"], tech)

    from science_cli.core.session import load_session
    sess = load_session()
    active_proto = sess.get("last_protocol", "")

    # Determine which files to display and whether to show protocol column
    display_files = []
    show_proto = True
    if active_proto:
        active_protocol_files = [
            f for f in files 
            if f.name in file_step_map 
            and file_step_map[f.name][0] == active_proto
            and file_step_map[f.name][2] == "uv-vis"
        ]
        if active_protocol_files:
            display_files = active_protocol_files
            show_proto = False
        else:
            # Fallback to all files
            display_files = files
            show_proto = True
    else:
        display_files = files
        show_proto = True

    # Build display items with step/protocol info
    from science_cli.core.fzf_utils import build_fzf_display
    display_items = []
    for f in display_files:
        name = f.name
        if name in file_step_map:
            proto, step, tech = file_step_map[name]
            display_items.append(build_fzf_display(proto, step, name, show_protocol=show_proto))
        else:
            display_items.append(name)

    selected = fzf_select(
        items=display_items,
        prompt=prompt,
        multi=True,
        preview=f"head -n 20 {raw_dir}/$(echo {{}} | awk '{{print $NF}}')",
        preview_window="right:50%:border-sharp",
    )
    if not selected:
        return []

    # Strip prefix columns to get clean filenames using the last token
    selected = [s.split()[-1] for s in selected]
    return [str(raw_dir / s) for s in selected]


def uv_vis_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("uv-vis")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "ls":
        _uv_ls(sub_args)
    elif sub == "info":
        _uv_info(sub_args)
    elif sub == "plot":
        console.print("[yellow]⚠️  'sci uv-vis plot' is deprecated. Use 'sci plot --technique uv-vis [FLAGS]' instead.[/yellow]")
        _uv_plot(sub_args)
    elif sub == "analyze":
        console.print("[yellow]⚠️  'uv-vis analyze' is deprecated. Use 'analyze --technique uv-vis' instead.[/yellow]")
        _uv_analyze(sub_args)
    else:
        console.print(f"[yellow]Unknown uv-vis subcommand: {sub}[/yellow]")
        show_command_help("uv-vis")


def _uv_ls(args: list) -> None:
    pos, flags = _parse_flags(args)
    raw_dir = _get_project_raw_dir()

    if not raw_dir:
        console.print("[yellow]No project open. Open a project first.[/yellow]")
        return

    uv_files = _get_uv_files(raw_dir)
    if not uv_files:
        console.print("[yellow]No UV-Vis files found.[/yellow]")
        return

    table = Table(title="UV-Vis Files", border_style="cyan")
    table.add_column("File", style="bold white")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Path", style="dim")

    for f in uv_files:
        size = f.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
        table.add_row(f.name, size_str, str(f.parent))

    console.print(table)


def _uv_info(args: list) -> None:
    pos, flags = _parse_flags(args)
    
    if not pos:
        files = _uv_fzf_pick_multi("Select UV-Vis file(s) for info")
        if not files:
            return
    else:
        files = [_resolve_file(f) for f in pos]
        files = [f for f in files if f]

    if not files:
        console.print("[red]No valid file(s) found.[/red]")
        return

    for filepath in files:
        p = Path(filepath)

        try:
            df, info = load_data_file(str(p), technique="uv-vis")
        except Exception as e:
            console.print(f"[red]Failed to load file {p.name}: {e}[/red]")
            continue

        console.print(f"\n[bold]UV-Vis File Info: {p.name}[/bold]")
        console.print(f"  Data Points: {len(df)}")
        console.print(f"  Columns: {', '.join(df.columns)}")

        for col in df.columns:
            vals = df[col].dropna()
            if not vals.empty:
                try:
                    console.print(f"    - {col}: min={vals.min():.2f}, max={vals.max():.2f}")
                except Exception:
                    pass


def _uv_plot(args: list) -> None:
    pos, flags = _parse_flags(args)

    if not pos:
        selected_files = _uv_fzf_pick_multi("Select UV-Vis file(s) to plot")
        if not selected_files:
            return

        # Pre-fill flags from uv-vis template
        all_flags: dict = {}
        from science_cli.theme import template_to_flags
        all_flags.update(template_to_flags("uv-vis"))
        from science_cli.core.config import get_plot_labels
        all_flags.update(get_plot_labels("uv-vis"))

        # Apply active theme defaults
        from science_cli.core.session import get_active_theme
        from science_cli.theme import apply_theme
        apply_theme(get_active_theme())

        # Prompt 1: Style / analysis flags with UV-Vis hints
        from science_cli.cli.commands.plot import _technique_hints
        style_hint = _technique_hints("uv-vis").get(
            "plot_style",
            "--type line | --color | --linewidth",
        )
        rprint(f"  [dim]# {style_hint}[/dim]")
        raw_style = input("  Style options (Enter to skip — uses theme defaults): ").strip()
        if raw_style:
            _, style_flags = _parse_flags(raw_style.split())
            all_flags.update(style_flags)

        # Prompt 2: Figure / output flags
        fig_hint = _technique_hints("uv-vis").get(
            "figure",
            "-n name.pdf | --xlabel | --ylabel | --grid | --zoom x1,x2,y1,y2",
        )
        rprint(f"  [dim]# {fig_hint}[/dim]")
        raw_figure = input("  Figure options (Enter to skip — uses theme defaults): ").strip()
        if raw_figure:
            _, figure_flags = _parse_flags(raw_figure.split())
            all_flags.update(figure_flags)

        # Combine with CLI flags
        all_flags.update(flags)
        all_flags["technique"] = "uv-vis"

        resolved = selected_files
    else:
        resolved = [_resolve_file(f) for f in pos]
        resolved = [f for f in resolved if f]
        all_flags = flags

    if not resolved:
        console.print("[red]No valid file(s) found.[/red]")
        return

    # Enforce boundaries on all files
    from science_cli.core.technique import detect_technique
    for f in resolved:
        tech = detect_technique(Path(f).name)
        if tech != "uv-vis":
            console.print(f"[red]Error: File '{Path(f).name}' is not identified as UV-Vis (detected: '{tech}'). Enforcing UV-Vis boundaries.[/red]")
            return

    from science_cli.cli.commands.plot import _do_plot, _do_overlap

    if len(resolved) == 1:
        _do_plot(resolved[0], all_flags, technique="uv-vis")
    else:
        # Symmetrically determine overlay vs individual mode
        overlay_mode = "--overlay" in args
        all_mode = "--all" in args

        if not overlay_mode and not all_mode:
            choice = input("  Overlay all (o) or individual plots (i)? [o/i] ").strip().lower()
            if choice == "i":
                all_mode = True
            else:
                overlay_mode = True

        if all_mode:
            for f in resolved:
                _do_plot(f, all_flags, technique="uv-vis")
        else:
            _do_overlap(resolved, all_flags, technique="uv-vis")


def _uv_analyze(args: list) -> None:
    pos, flags = _parse_flags(args)

    if not pos:
        resolved = _uv_fzf_pick_multi("Select UV-Vis file(s) for analysis")
        if not resolved:
            return
    else:
        resolved = [_resolve_file(f) for f in pos]
        resolved = [f for f in resolved if f]

    if not resolved:
        console.print("[red]No valid file(s) found.[/red]")
        return

    # Enforce boundaries on all files
    from science_cli.core.technique import detect_technique
    for f in resolved:
        p = Path(f)
        tech = detect_technique(p.name)

        if tech != "uv-vis":
            console.print(f"[red]Error: File '{p.name}' is not a UV-Vis technique (detected: '{tech}'). Enforcing UV-Vis boundaries.[/red]")
            continue

        try:
            df, info = load_data_file(str(p), technique="uv-vis")
        except Exception as e:
            console.print(f"[red]Failed to load file {p.name}: {e}[/red]")
            continue

        cols = list(df.columns)
        if len(cols) < 2:
            console.print(f"[red]Not enough columns in {p.name}.[/red]")
            continue

        x = df[cols[0]].values.astype(float)
        y = df[cols[1]].values.astype(float)
        mask = ~(np.isnan(x) | np.isnan(y))

        if not mask.any():
            console.print(f"[red]No valid data points in {p.name}.[/red]")
            continue

        x = x[mask]
        y = y[mask]

        console.print(f"\n[bold]UV-Vis Analysis: {p.name}[/bold]")
        console.print(f"  Data points: {len(x)}")
        console.print(f"  Wavelength range: {x.min():.1f} nm to {x.max():.1f} nm")

        # Perform analysis
        max_val = float(y.max())
        min_val = float(y.min())
        idx_max = int(y.argmax())
        idx_min = int(y.argmin())

        console.print(f"  Max value: {max_val:.4f} at {x[idx_max]:.1f} nm")
        console.print(f"  Min value: {min_val:.4f} at {x[idx_min]:.1f} nm")

        dy = np.gradient(y, x)
        idx_max_slope = int(np.abs(dy).argmax())
        console.print(f"  Inflection Point (max absolute slope): {x[idx_max_slope]:.1f} nm (slope={dy[idx_max_slope]:.4e})")

        # Save CSV outputs
        out_dir = _get_results_dir(str(p))
        prefix = flags.get("name") or p.stem

        import pandas as pd
        res_df = pd.DataFrame({
            "wavelength(nm)": x,
            "intensity": y,
            "derivative": dy
        })
        res_csv = out_dir / f"{prefix}_analysis.csv"
        res_df.to_csv(res_csv, index=False)
        console.print(f"  [bold green]✓[/bold green] Saved results to: {res_csv}")

        # Emit manifest
        from science_cli.core.manifest import emit_manifest
        from science_cli.core.project import get_current_project_path
        emit_manifest(
            output_dir=out_dir,
            command=f"uv-vis analyze {str(p)}",
            source_files=[str(p)],
            output_files=[str(res_csv)],
            technique="uv-vis",
            parameters=flags,
            project=get_current_project_path().name if get_current_project_path() else "",
        )

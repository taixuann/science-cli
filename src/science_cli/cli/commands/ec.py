"""ec command handler — specialized electrochemistry plotting and analysis with FZF integration."""

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


def _get_ec_files(raw_dir: Path) -> list[Path]:
    from science_cli.core.technique import detect_technique
    return sorted(
        f for f in raw_dir.iterdir()
        if f.is_file()
        and (detect_technique(f.name).startswith("ec-") or any(p in f.name.lower() for p in ["_cv", "_ca", "_eis", ".mpt", ".eis"]))
    )


def _ec_fzf_pick_multi(prompt: str = "Select Electrochemistry file(s)") -> list[str]:
    raw_dir = _get_project_raw_dir()
    if not raw_dir:
        console.print("[yellow]No project open.[/yellow]")
        return []

    files = _get_ec_files(raw_dir)
    if not files:
        console.print("[yellow]No Electrochemistry files found.[/yellow]")
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
            and file_step_map[f.name][2].startswith("ec-")
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


def ec_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("ec")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "ls":
        _ec_ls(sub_args)
    elif sub == "info":
        _ec_info(sub_args)
    elif sub == "plot":
        console.print("[yellow]⚠️  'sci ec plot' is deprecated. Use 'sci plot --technique <ec-cv|ec-ca|ec-eis> [FLAGS]' instead.[/yellow]")
        _ec_plot(sub_args)
    elif sub == "analyze":
        _ec_analyze(sub_args)
    else:
        console.print(f"[yellow]Unknown ec subcommand: {sub}[/yellow]")
        show_command_help("ec")


def _ec_ls(args: list) -> None:
    pos, flags = _parse_flags(args)
    raw_dir = _get_project_raw_dir()

    if not raw_dir:
        console.print("[yellow]No project open. Open a project first.[/yellow]")
        return

    ec_files = _get_ec_files(raw_dir)
    if not ec_files:
        console.print("[yellow]No Electrochemistry files found.[/yellow]")
        return

    from science_cli.core.technique import detect_technique, technique_label

    table = Table(title="Electrochemistry Files", border_style="cyan")
    table.add_column("File", style="bold white")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Technique", style="yellow")
    table.add_column("Path", style="dim")

    for f in ec_files:
        size = f.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
        tech = detect_technique(f.name)
        label = technique_label(tech) if tech else "Unknown"
        table.add_row(f.name, size_str, label, str(f.parent))

    console.print(table)


def _ec_info(args: list) -> None:
    pos, flags = _parse_flags(args)
    
    if not pos:
        files = _ec_fzf_pick_multi("Select Electrochemistry file(s) for info")
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
        from science_cli.core.technique import detect_technique
        tech = detect_technique(p.name)

        try:
            df, info = load_data_file(str(p))
        except Exception as e:
            console.print(f"[red]Failed to load file {p.name}: {e}[/red]")
            continue

        console.print(f"\n[bold]EC File Info: {p.name}[/bold]")
        console.print(f"  Detected Technique: [yellow]{tech}[/yellow]")
        console.print(f"  Data Points: {len(df)}")
        console.print(f"  Columns: {', '.join(df.columns)}")

        for col in df.columns:
            vals = df[col].dropna()
            if not vals.empty:
                try:
                    console.print(f"    - {col}: min={vals.min():.4e}, max={vals.max():.4e}")
                except Exception:
                    pass


def _ec_plot(args: list) -> None:
    pos, flags = _parse_flags(args)

    # Determine if we should open FZF
    # Symmetrically with plot.py: if no files are provided (either args is empty or the first arg starts with a flag)
    if not pos:
        selected_files = _ec_fzf_pick_multi("Select Electrochemistry file(s) to plot")
        if not selected_files:
            return
        
        # Symmetrically auto-detect technique from the first file
        from science_cli.core.technique import detect_technique
        auto_technique = detect_technique(Path(selected_files[0]).name)

        # Pre-fill flags from technique template + config labels
        all_flags: dict = {}
        if auto_technique:
            from science_cli.theme import template_to_flags
            all_flags.update(template_to_flags(auto_technique))
            from science_cli.core.config import get_plot_labels
            all_flags.update(get_plot_labels(auto_technique))

        # Apply active theme defaults
        from science_cli.core.session import get_active_theme
        from science_cli.theme import apply_theme
        apply_theme(get_active_theme())

        if auto_technique:
            rprint(f"  [bold]Detected technique:[/bold] {auto_technique}")

        # Prompt 1: Style / analysis flags with EC hints
        from science_cli.cli.commands.plot import _technique_hints
        style_hint = _technique_hints(auto_technique).get(
            "plot_style",
            "--type line|scatter | --color | --linewidth | --linestyle",
        )
        rprint(f"  [dim]# {style_hint}[/dim]")
        raw_style = input("  Style / analysis options (Enter to skip — uses theme defaults): ").strip()
        if raw_style:
            _, style_flags = _parse_flags(raw_style.split())
            all_flags.update(style_flags)

        # Prompt 2: Figure / output flags
        fig_hint = _technique_hints(auto_technique).get(
            "figure",
            "-n name.pdf | --xlabel | --ylabel | --grid | --legend",
        )
        rprint(f"  [dim]# {fig_hint}[/dim]")
        raw_figure = input("  Figure options (Enter to skip — uses theme defaults): ").strip()
        if raw_figure:
            _, figure_flags = _parse_flags(raw_figure.split())
            all_flags.update(figure_flags)

        # Combine with CLI-passed flags
        all_flags.update(flags)
        all_flags["technique"] = auto_technique

        resolved = selected_files
    else:
        # Direct files provided via CLI
        resolved = [_resolve_file(f) for f in pos]
        resolved = [f for f in resolved if f]
        all_flags = flags

    if not resolved:
        console.print("[red]No valid file(s) found.[/red]")
        return

    # Enforce technique boundaries on all files
    from science_cli.core.technique import detect_technique
    for f in resolved:
        tech = detect_technique(Path(f).name)
        if not tech.startswith("ec-"):
            console.print(f"[red]Error: File '{Path(f).name}' is not identified as an Electrochemistry technique (detected: '{tech}'). Enforcing EC boundaries.[/red]")
            return

    # Single vs multiple files
    from science_cli.cli.commands.plot import _do_plot, _do_overlap

    # Auto-detect technique for plotting execution
    first_tech = detect_technique(Path(resolved[0]).name)

    if len(resolved) == 1:
        _do_plot(resolved[0], all_flags, technique=first_tech)
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
                f_tech = detect_technique(Path(f).name)
                _do_plot(f, all_flags, technique=f_tech)
        else:
            _do_overlap(resolved, all_flags, technique=first_tech)


def _ec_analyze(args: list) -> None:
    pos, flags = _parse_flags(args)

    if not pos:
        resolved = _ec_fzf_pick_multi("Select Electrochemistry file(s) for analysis")
        if not resolved:
            return
    else:
        resolved = [_resolve_file(f) for f in pos]
        resolved = [f for f in resolved if f]

    if not resolved:
        console.print("[red]No valid file(s) found.[/red]")
        return

    # Enforce technique boundaries on all files
    from science_cli.core.technique import detect_technique
    from science_cli.cli.commands.analyze import _analyze_cv, _analyze_ca, _analyze_eis

    for f in resolved:
        p = Path(f)
        tech = detect_technique(p.name)

        if not tech.startswith("ec-"):
            console.print(f"[red]Error: File '{p.name}' is not an Electrochemistry technique (detected: '{tech}'). Enforcing EC boundaries.[/red]")
            continue

        if tech == "ec-cv":
            _analyze_cv(str(p), flags)
        elif tech == "ec-ca":
            _analyze_ca(str(p), flags)
        elif tech == "ec-eis":
            _analyze_eis(str(p), flags)
        else:
            console.print(f"[yellow]Unknown EC technique: {tech}. Running CV analysis as default.[/yellow]")
            _analyze_cv(str(p), flags)

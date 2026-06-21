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
            # Normalize --linear / --log
            if key in ("linear", "log"):
                flags["scale"] = key
                i += 1
                continue
            if i + 1 < len(args) and not is_flag(args[i + 1]):
                i += 1
                tokens = []
                while i < len(args) and not is_flag(args[i]):
                    tokens.append(args[i])
                    i += 1
                flags[key] = " ".join(tokens)
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
        # Fallback: scan protocol step folders
        from science_cli.core.paths import ProjectPaths
        paths = ProjectPaths(proj)
        for py in paths.list_protocol_yamls():
            pname = py.stem
            with open(py) as f:
                import yaml
                proto_data = yaml.safe_load(f) or {}
            for s in proto_data.get("steps", []):
                step_dir = paths.step_dir(pname, s["name"])
                if not step_dir.exists():
                    continue
                for entry in s.get("files", []):
                    fname = entry["file"] if isinstance(entry, dict) else entry
                    if fname == name:
                        found = step_dir / fname
                        if found.exists():
                            return str(found)
    return ""


def _detect_technique(filename: str) -> str:
    from science_cli.core.technique import detect_technique
    t = detect_technique(filename)
    return t.lower() if t else ""


def _detect_study(filename: str) -> str | None:
    """Detect study from filename, returning study name or None."""
    from science_cli.core.config import detect_study_from_filename
    return detect_study_from_filename(filename)


def _detect_device_type(
    study_name: str | None = None,
    filepath: str = "",
    flags: dict | None = None,
) -> str | None:
    """Auto-detect device_type from multiple sources.

    Resolution order:
        1. ``flags["device-type"]`` or ``flags["dt"]`` — explicit CLI override
        2. Protocol YAML ``devices:`` field — from session's active protocol
        3. Reverse lookup — which device_type lists this study? If unique, return it
        4. ``None`` — no device type (base plotter behavior)

    Args:
        study_name: Study name in "technique:study-name" format or legacy name.
        filepath: Path to the data file (for protocol YAML lookup context).
        flags: Parsed CLI flags dict (may contain ``device-type`` / ``dt``).

    Returns:
        Device type slug (e.g. ``"volatile-memristor"``) or ``None``.
    """
    # 1. Explicit CLI flag
    if flags:
        dt = flags.get("device-type") or flags.get("dt", "")
        if dt:
            return str(dt)

    # 2. Protocol YAML devices field
    if filepath:
        try:
            from science_cli.core.paths import ProjectPaths
            from science_cli.core.project import get_current_project_path
            from science_cli.core.session import load_session

            proj = get_current_project_path()
            session = load_session()
            pname = session.get("last_protocol", "")

            if pname and proj:
                paths = ProjectPaths(proj)
                yaml_path = paths.protocol_yaml(pname)
                if yaml_path.exists():
                    import yaml
                    with open(yaml_path) as f:
                        proto = yaml.safe_load(f) or {}
                    devices_field = proto.get("devices", "")
                    if devices_field and devices_field != "general":
                        return str(devices_field)
        except Exception:
            pass  # Session or project not available; fall through

    # 3. Reverse lookup: which device types include this study?
    if study_name:
        try:
            from science_cli.core.config import load_global_config
            device_types = load_global_config().get("device_types", {})
            matching: list[str] = []
            for dt_slug, dt_cfg in device_types.items():
                if study_name in dt_cfg.get("studies", []):
                    matching.append(dt_slug)
            # Only return if exactly one device type matches
            if len(matching) == 1:
                return matching[0]
        except Exception:
            pass

    return None


from science_cli.core.device_resolver import resolve_device as _resolve_device


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
    "pulse-endurance": {
        "plot_style": "--marker o | --markersize 10 | --color | --linewidth",
        "figure": "-n endurance.pdf | --xlabel Cycle (log) | --ylabel Resistance (Ω) | --zoom x1,x2,y1,y2",
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
        "figure": "-n spectrum.pdf | --xlabel Raman shift (cm\u207b\u00b9) | --ylabel Intensity (counts) | --grid | --zoom x1,x2",
    },
    "uv-vis": {
        "plot_style": "--type line | --color | --linewidth",
        "figure": "-n uv-vis.pdf | --xlabel Wavelength (nm) | --ylabel Transmission (%) | --grid | --zoom x1,x2,y1,y2",
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

    positionals, flags = _parse_flags(args)
    has_technique_flag = bool(flags.get("technique") or flags.get("t") or flags.get("study") or flags.get("s"))
    if positionals or has_technique_flag:
        _plot_direct(positionals, args)
        return

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

    from science_cli.core.fzf.display import fzf_select
    from science_cli.core.paths import ProjectPaths
    paths = ProjectPaths(proj)
    file_step_map: dict[str, tuple[str, str, str]] = {}
    for py in paths.list_protocol_yamls():
        pname = py.stem
        with open(py) as f:
            proto_data = __import__("yaml").safe_load(f) or {}
        for s in proto_data.get("steps", []):
            study = s.get("study", "")
            for entry in s.get("files", []):
                fname = entry["file"] if isinstance(entry, dict) else entry
                file_step_map[fname] = (pname, s["name"], study)

    # Also scan protocol step folders for files listed in protocol.yaml
    # but not found in data/raw/ (e.g. _extracted-list.csv in 5_pulse-endurance/)
    raw_names = {f.name for f in files}
    for py in paths.list_protocol_yamls():
        pname = py.stem
        with open(py) as f:
            proto_data = __import__("yaml").safe_load(f) or {}
        for s in proto_data.get("steps", []):
            step_dir = paths.step_dir(pname, s["name"])
            if not step_dir.exists():
                continue
            for entry in s.get("files", []):
                fname = entry["file"] if isinstance(entry, dict) else entry
                if fname not in raw_names:
                    step_file = step_dir / fname
                    if step_file.exists():
                        files.append(step_file)
                        raw_names.add(fname)

    from science_cli.core.session import load_session
    sess = load_session()
    active_proto = sess.get("last_protocol", "")

    display_files = []
    show_proto = True
    if active_proto:
        active_protocol_files = [f for f in files if f.name in file_step_map and file_step_map[f.name][0] == active_proto]
        if active_protocol_files:
            display_files = active_protocol_files
            show_proto = False
        else:
            display_files = files
            show_proto = True
    else:
        display_files = files
        show_proto = True

    from science_cli.core.fzf.display import build_fzf_display
    from science_cli.core.fzf.columns import status_badge_for_file, get_step_columns
    from science_cli.cli.commands.results_status import load_status
    status = load_status(proj)
    display_items: list[str] = []
    display_to_name: dict[str, str] = {}
    for f in display_files:
        name = f.name
        if name in file_step_map:
            proto, step, study = file_step_map[name]
            technique = _detect_technique(name)
            instrument = _resolve_device(technique, str(f))
            # Try to load study-specific metadata from protocol.yaml
            metadata = get_step_columns(proj, step, study)
            if not metadata:
                metadata = {"technique": technique, "instrument": instrument}
            rel_key = f"{proto}/{step}/{name}"
            badge = status_badge_for_file(rel_key, status)
            display = build_fzf_display(
                proto, step, name, show_protocol=show_proto,
                metadata=metadata, study_name=study, status_badge=badge,
            )
            display_to_name[display.strip()] = name
            display_items.append(display)
        else:
            display_to_name[name] = name
            display_items.append(name)

    prompt = f"{active_proto} | Select file(s) >" if active_proto else "Select file(s) (Tab to multi-select):"
    selected = fzf_select(
        items=display_items,
        prompt=prompt,
        multi=True,
    )
    if not selected:
        return

    selected = [display_to_name.get(s.strip(), s) for s in selected]

    rprint(f"\n[bold]Selected {len(selected)} file(s):[/bold]")
    for f in selected:
        step_info = ""
        if f in file_step_map:
            proto, step, _ = file_step_map[f]
            step_info = f"  [dim]→ {proto}/{step}[/dim]"
        rprint(f"  [dim]• {f}[/dim]{step_info}")
    rprint("")

    from science_cli.core.session import load_session
    session = load_session()
    current_protocol = session.get("last_protocol", "")
    auto_technique = ""
    auto_study = None
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
    if not auto_technique and selected:
        from science_cli.core import technique as _tech_module
        auto_technique, auto_study = _tech_module.detect_study_or_technique(selected[0])

    all_flags: dict = {}
    if auto_technique:
        from science_cli.theme import template_to_flags
        all_flags.update(template_to_flags(auto_technique))
        from science_cli.core.config import get_plot_labels
        all_flags.update(get_plot_labels(auto_technique))

    if extra_args:
        _, cli_flags = _parse_flags(extra_args)
        all_flags.update(cli_flags)

    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    if auto_technique:
        rprint(f"  [bold]Detected technique:[/bold] {auto_technique}")
        if all_flags:
            rprint(f"  [bold]Pre-filled defaults:[/bold] [dim]{all_flags}[/dim]")

    # ── Interactive style / figure options form ──
    from rich.prompt import Prompt
    import matplotlib as mpl

    theme_lw = mpl.rcParams.get("lines.linewidth", 1.0)
    theme_ms = mpl.rcParams.get("lines.markersize", 4)
    theme_ls = mpl.rcParams.get("lines.linestyle", "solid")
    theme_marker = mpl.rcParams.get("lines.marker", "")
    theme_dpi = mpl.rcParams.get("savefig.dpi", 600)

    rprint("  [bold]Figure options[/bold] [dim](press Enter to accept default, type value to override)[/dim]")
    rprint("")

    fields = [
        ("name",        "Output filename",                              "",          "auto-generate"),
        ("label",       "Legend labels (comma-separated)",              "",          "none"),
        ("markersize",  "Marker size",                                  str(theme_ms), None),
        ("color",       "Line/marker color",                            "",          "theme default"),
        ("linewidth",   "Line width",                                   str(theme_lw), None),
        ("linestyle",   "Line style",                                   theme_ls,    None),
        ("marker",      "Marker style",                                 theme_marker or "", "none"),
        ("dpi",         "Figure DPI",                                   str(theme_dpi), None),
        ("grid",        "Show grid (y/N)",                              "",          "no"),
        ("legend",      "Show legend (y/N)",                            "",          "no"),
    ]

    for key, label, default, fallback_text in fields:
        if default:
            raw = Prompt.ask(f"  {label}", default=default)
        else:
            hint = fallback_text or "skip"
            raw = input(f"  {label} [{hint}]: ").strip()

        if key in ("grid", "legend"):
            if raw and raw.lower() in ("y", "yes", "true", "1"):
                all_flags[key] = True
            continue
        if raw:
            if key == "label":
                all_flags["label-name"] = raw
            elif key == "name":
                all_flags["n"] = raw
            elif key in ("markersize", "linewidth", "dpi"):
                try:
                    all_flags[key] = float(raw)
                except ValueError:
                    rprint(f"  [yellow]Invalid {key}, skipping.[/yellow]")
            else:
                all_flags[key] = raw

    resolved = [_resolve_file(f) for f in selected]
    resolved = [f for f in resolved if f]

    if not resolved:
        console.print("[yellow]No valid files selected.[/yellow]")
        return

    overlay_mode = extra_args and "--overlay" in extra_args
    all_mode = extra_args and "--all" in extra_args

    if not overlay_mode and not all_mode and len(resolved) > 1:
        choice = input("  Overlay all (o) or individual plots (i)? [o/i] ").strip().lower()
        if choice == "i":
            all_mode = True
        else:
            overlay_mode = True

    # Detect device_type from flags, protocol YAML, or reverse study lookup
    device_type = _detect_device_type(
        study_name=auto_study,
        filepath=resolved[0],
        flags=all_flags,
    )

    if all_mode:
        # Check if any selected file has an interactive plot menu — if so,
        # show the menu once and apply to all files
        first_study = None
        for f in resolved:
            s = _detect_study(Path(f).name) or auto_study
            if s:
                first_study = s
                break
        if first_study:
            try:
                from science_cli.core.interactive_menu import dispatch
                resolved_paths = [Path(f) for f in resolved]
                dispatch(study_key=first_study, menu_type="plot", file_paths=resolved_paths)
                console.print(f"[dim]Applied plot to {len(resolved)} file(s)[/dim]")
                return
            except (KeyError, ImportError, ModuleNotFoundError):
                pass  # No interactive menu — fall through to default
        for f in resolved:
            tech = _detect_technique(Path(f).name) or auto_technique
            study = _detect_study(Path(f).name) or auto_study
            _do_plot(f, all_flags, tech, study_name=study, device_type=device_type)
    else:
        _do_overlap(resolved, all_flags, auto_technique, study_name=auto_study, device_type=device_type)


def _plot_direct(files: list, rest_args: list) -> None:
    _, flags = _parse_flags(rest_args)

    resolved = [_resolve_file(f) for f in files]
    resolved = [f for f in resolved if f]

    if not resolved:
        technique = flags.get("technique") or flags.get("t", "")
        study_name = flags.get("s") or flags.get("study", "")
        if technique or study_name:
            rprint(f"[bold]Technique:[/bold] {technique or study_name}")
        else:
            console.print("[red]File(s) not found. Provide a filename or use 'sci plot' (interactive mode).[/red]")
        return

    technique = flags.get("technique") or flags.get("t", "")
    study_name = flags.get("s") or flags.get("study", "")
    if study_name and not technique:
        from science_cli.core.config import resolve_technique_from_study
        technique = resolve_technique_from_study(study_name)
    if not technique and resolved:
        from science_cli.core import technique as _tech_module
        tech, study_name = _tech_module.detect_study_or_technique(Path(resolved[0]).name)
        technique = tech

    if technique:
        from science_cli.core.config import get_plot_labels
        from science_cli.theme import template_to_flags
        merged = {}
        merged.update(template_to_flags(technique))
        merged.update(get_plot_labels(technique))
        merged.update(flags)
        flags = merged

    # Detect device_type from flags, protocol YAML, or reverse study lookup
    device_type = _detect_device_type(
        study_name=study_name,
        filepath=resolved[0],
        flags=flags,
    )

    describe = flags.get("describe")
    if describe is not False and describe is not None:
        # Show text describe table
        from science_cli.plot.registry import _show_describe
        for fp in resolved:
            study = study_name or _detect_study(Path(fp).name)
            fields = describe if isinstance(describe, str) else None
            _show_describe(fp, study or "", fields)
        # Also enable the waveform subfigure on the plot
        flags["show_waveform"] = True

    if len(resolved) == 1:
        _dispatch_technique_plot(resolved[0], flags, technique, study_name=study_name, device_type=device_type)
    else:
        _do_overlap(resolved, flags, technique, study_name=study_name, device_type=device_type)


def _resolve_xy_columns(
    df, info: dict, technique: str = ""
) -> tuple:
    """Resolve x/y columns from DataFrame, trying config-based resolution first.

    Config-based resolution reads ``instrument_config.column_mapping`` from the
    *info* dict (populated by the device-aware data loader).  Falls back to
    hardcoded column-name heuristics when no config is available (legacy files
    loaded without device config).

    Returns:
        Tuple ``(x_values, y_values, x_label, y_label)`` where labels are
        column names suitable for axis labelling.
    """
    import numpy as np

    xcol, ycol = "", ""

    # ── Attempt 1: Config-based resolution via instrument_config ─────────
    instrument_cfg = info.get("instrument_config", {})
    column_mapping = instrument_cfg.get("column_mapping", {})
    if column_mapping:
        x_key = column_mapping.get("x", "")
        y_key = column_mapping.get("y", "")
        if x_key and y_key:
            # After device-aware data loading, column names match the keys
            # (e.g. ``time``, ``current``) — no further lookup needed.
            if x_key in df.columns and y_key in df.columns:
                current_sign = instrument_cfg.get("current_sign", 1)
                x = df[x_key].values.astype(float)
                y = df[y_key].values.astype(float)
                if current_sign != 1 and current_sign is not None:
                    y = y * current_sign

                mask = ~(np.isnan(x) | np.isnan(y))
                return x[mask], y[mask], x_key, y_key

    # ── Attempt 2: Hardcoded column-name heuristics ──────────────────────

    if technique == "ec-ca":
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
        numeric = [
            c
            for c in df.select_dtypes(include=[np.number]).columns
            if c not in ("Index", "index")
        ]
        if len(numeric) >= 2:
            xcol, ycol = numeric[0], numeric[1]

    # ── Attempt 3: Generic fallback — first two numeric columns ─────────
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

    if technique in ("ec-ca", "ec-cv") and xcol not in (
        "Corrected time (s)", "corrected time",
    ):
        x_numeric = np.asarray(x, dtype=float)
        if np.any(x_numeric > 100):
            x = x_numeric - x_numeric[0]

    mask = ~(np.isnan(x.astype(float)) | np.isnan(y.astype(float)))
    return x[mask], y[mask], xcol, ycol


def _dispatch_technique_plot(
    filepath: str,
    flags: dict,
    technique: str,
    study_name: str | None = None,
    device_type: str | None = None,
) -> None:
    """Route to technique/study-specific plotter via registry.

    When ``device_type`` is provided, the resolved StudyPlotter may
    carry device-type-specific overrides (plot_fn, overlay_fn, flags).
    """
    from science_cli.plot.registry import _init_dedicated_plotters, resolve_study_plotter
    _init_dedicated_plotters()

    plotter = None
    if study_name:
        plotter = resolve_study_plotter(study_name, device_type=device_type)
    if plotter is None and technique:
        plotter = resolve_study_plotter(technique, device_type=device_type)
    if plotter is not None:
        plotter.plot_fn(filepath, flags)
    else:
        _do_plot(filepath, flags, technique, study_name=study_name, device_type=device_type)


def _do_plot(
    filepath: str,
    flags: dict,
    technique: str = "",
    study_name: str | None = None,
    device_type: str | None = None,
) -> None:
    from science_cli.core.data_loader import load_data_file

    # Route through study plotter when available (handles NaN, sort, filter,
    # current_sign, dual_axis, series colors, etc.)
    if study_name:
        try:
            from science_cli.plot.registry import _init_dedicated_plotters, resolve_study_plotter
            _init_dedicated_plotters()
            sp = resolve_study_plotter(study_name)
            if sp and sp.plot_fn:
                sp.plot_fn(filepath, flags, study_name=study_name)
                return
        except (ImportError, Exception):
            pass

    try:
        load_kwargs = {}
        if study_name:
            load_kwargs["study_name"] = study_name
        if technique:
            device = _resolve_device(technique, filepath, study_name=study_name)
            if device:
                load_kwargs["technique"] = technique
                load_kwargs["device"] = device
        df, info = load_data_file(filepath, **load_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to load file: {e}[/red]")
        return

    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt

    apply_theme(get_active_theme())

    show_waveform = flags.get("show_waveform", False)
    if show_waveform:
        fig, (ax, axw) = plt.subplots(1, 2, figsize=(_figsize(flags)[0] * 2, _figsize(flags)[1]))
    else:
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
    _def_lw = mpl.rcParams.get("lines.linewidth", 1.0)
    _def_ms = mpl.rcParams.get("lines.markersize", 4)
    linewidth = float(flags.get("linewidth", _def_lw)) if flags.get("linewidth") else _def_lw
    linestyle = flags.get("linestyle", mpl.rcParams.get("lines.linestyle", "solid"))
    marker = flags.get("marker", None)
    markersize = float(flags.get("markersize", _def_ms)) if flags.get("markersize") else _def_ms
    cmap = flags.get("cmap", None)

    plot_kw = {}
    if color:
        plot_kw["color"] = color
    if marker:
        plot_kw["marker"] = marker
        plot_kw["markersize"] = markersize

    if technique == "iv-sweep" and flags.get("gradient"):
        import numpy as np
        from matplotlib.collections import LineCollection
        cmap_name = flags.get("cmap", "viridis")
        _cmap = plt.get_cmap(cmap_name)
        pts = np.column_stack([x, y]).reshape(-1, 1, 2)
        segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
        lc = LineCollection(segs, cmap=_cmap, linewidth=linewidth, linestyle=linestyle)
        lc.set_array(np.linspace(0, 1, len(segs)))
        ax.add_collection(lc)
        ax.autoscale()
        sm = plt.cm.ScalarMappable(cmap=_cmap)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label("Sweep progression")
    elif plot_type == "line":
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

    # ── Waveform subfigure (right panel) ──
    if show_waveform:
        from science_cli.plot.generic import _plot_waveform_panel
        waveform_pattern = info.get("analysis", {}).get("waveform_pattern")
        if waveform_pattern and isinstance(waveform_pattern, list) and len(waveform_pattern) >= 2:
            _plot_waveform_panel(axw, waveform_pattern)
        else:
            axw.text(0.5, 0.5, "No waveform data available",
                     ha="center", va="center", transform=axw.transAxes,
                     fontsize=9, color="gray")

    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    # Use study_name for output prefix if available, fall back to technique
    prefix = ""
    if study_name:
        # Extract study name from "technique:study-name" format
        prefix = study_name.split(":")[-1] if ":" in study_name else study_name
    elif technique:
        prefix = technique
    if prefix:
        out_name = flags.get("n") or flags.get("name", f"{prefix}_{stem}.pdf")
    else:
        out_name = flags.get("n") or flags.get("name", f"{stem}_plot.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    _def_dpi = int(mpl.rcParams.get("savefig.dpi", 600))
    dpi = int(flags.get("dpi", _def_dpi))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")

    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] Plot saved: {save_path}")

    from science_cli.core.manifest import emit_manifest
    from science_cli.core.project import get_current_project_path
    # Use study-based technique detection, not the old filename-based one
    manifest_tech = technique
    if study_name:
        from science_cli.core.config import resolve_technique_from_study
        manifest_tech = resolve_technique_from_study(study_name) or technique
    emit_manifest(
        output_dir=out_dir,
        command=f"plot {filepath}",
        source_files=[filepath],
        output_files=[str(save_path)],
        technique=manifest_tech,
        parameters=flags,
        project=get_current_project_path().name if get_current_project_path() else "",
    )


def _do_overlap(
    files: list,
    flags: dict,
    technique: str = "",
    study_name: str = "",
    device_type: str | None = None,
) -> None:
    """Overlay plots — route via registry if study/technique available.

    When ``device_type`` is provided, the resolved StudyPlotter may
    carry device-type-specific overlay overrides.
    """
    from science_cli.plot.registry import _init_dedicated_plotters, resolve_study_plotter
    _init_dedicated_plotters()

    plotter = None
    if study_name:
        plotter = resolve_study_plotter(study_name, device_type=device_type)
    if plotter is None and technique:
        plotter = resolve_study_plotter(technique, device_type=device_type)
    if plotter is not None:
        plotter.overlay_fn(files, flags)
        return
    _generic_overlay(files, flags, technique, study_name=study_name)


def _generic_overlay(files: list, flags: dict, technique: str = "",
                     study_name: str = "") -> None:
    """Generic overlay fallback."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt

    from science_cli.core.data_loader import load_data_file

    apply_theme(get_active_theme())
    fig, ax = plt.subplots(figsize=_figsize(flags))
    cycle = mpl.rcParams["axes.prop_cycle"]
    theme_colors = [entry["color"] for entry in cycle]
    colors = [theme_colors[i % len(theme_colors)] for i in range(len(files))]
    _def_lw = float(flags.get("linewidth", mpl.rcParams.get("lines.linewidth", 0.75)))

    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []

    for i, fp in enumerate(files):
        try:
            load_kwargs = {}
            if technique:
                device = _resolve_device(technique, fp)
                if device:
                    load_kwargs["technique"] = technique
                    load_kwargs["device"] = device
            df, info = load_data_file(fp, **load_kwargs)
            xi, yi, _, _ = _resolve_xy_columns(df, info, technique)
            if len(xi) == 0 or len(yi) == 0:
                continue
            label = label_list[i] if i < len(label_list) else Path(fp).stem
            ax.plot(xi, yi, label=label, color=colors[i], linewidth=_def_lw)
        except Exception:
            continue

    ax.legend()
    _apply_figure_kw(ax, flags, "overlay")

    out_dir = _get_results_dir(files[0])
    # Use study_name for output prefix if available, fall back to technique
    prefix = ""
    if study_name:
        # Extract study name from "technique:study-name" format
        prefix = study_name.split(":")[-1] if ":" in study_name else study_name
    elif technique:
        prefix = technique
    overlay_name = f"{prefix}_overlay.pdf" if prefix else "overlay.pdf"
    out_name = flags.get("n") or flags.get("name", overlay_name)
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    _def_dpi = int(mpl.rcParams.get("savefig.dpi", 600))
    dpi = int(flags.get("dpi", _def_dpi))
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
    import matplotlib as mpl
    return mpl.rcParams.get("figure.figsize", (3.46, 2.75))


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

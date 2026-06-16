"""raman command handler — list, inspect, plot, and analyze Raman spectra."""

from pathlib import Path

import numpy as np
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from science_cli.cli.help import show_command_help
from science_cli.core.data_loader import extract_raman_metadata, load_data_file
from science_cli.core.file_utils import is_flag

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


def _get_project_raw_dir() -> Path:
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if proj:
        raw_dir = proj / "data" / "raw"
        if raw_dir.exists():
            return raw_dir
    return Path()


def _get_raman_files(raw_dir: Path) -> list[Path]:
    return sorted(
        f for f in raw_dir.iterdir()
        if f.is_file()
        and any(p in f.name.lower() for p in ["_raman", "_sers", "_raman-sers"])
    )


def _raman_fzf_pick_single(prompt: str = "Select Raman file") -> str | None:
    """Launch fzf to pick a single Raman file. Returns resolved path or None."""
    raw_dir = _get_project_raw_dir()
    if not raw_dir:
        console.print("[yellow]No project open.[/yellow]")
        return None

    files = _get_raman_files(raw_dir)
    if not files:
        console.print("[yellow]No Raman files found.[/yellow]")
        return None

    from science_cli.core.fzf_utils import fzf_select

    items = []
    for f in files:
        meta = extract_raman_metadata(str(f))
        laser = meta.get("laser", "")[:10]
        nd_f = meta.get("nd_filter", "")
        acq = meta.get("acq_time_s", "")
        accum = meta.get("accumulations", "")
        rng = _raman_spectral_range(str(f))
        meta_tag = f"[{laser:>10}][{nd_f:>5}][{acq:>3}s][{accum}x][{rng:>16}]"
        items.append(f"{meta_tag} {f.name}")

    selected = fzf_select(
        items=items,
        prompt=prompt,
        multi=False,
        preview="",
    )
    if not selected:
        return None

    name = selected[0].split()[-1]
    return str(raw_dir / name)


def _raman_fzf_pick_multi(prompt: str = "Select Raman file(s)") -> list[str]:
    raw_dir = _get_project_raw_dir()
    if not raw_dir:
        console.print("[yellow]No project open.[/yellow]")
        return []

    files = _get_raman_files(raw_dir)
    if not files:
        console.print("[yellow]No Raman files found.[/yellow]")
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
            and file_step_map[f.name][2] == "raman"
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

    # Build display items with metadata + step/protocol info
    from science_cli.core.fzf_utils import build_fzf_display
    display_items = []
    for f in display_files:
        name = f.name
        meta = extract_raman_metadata(str(f))
        laser = meta.get("laser", "")[:10]
        nd_f = meta.get("nd_filter", "")
        acq = meta.get("acq_time_s", "")
        accum = meta.get("accumulations", "")
        rng = _raman_spectral_range(str(f))
        meta_tag = f"[{laser:>10}][{nd_f:>5}][{acq:>3}s][{accum}x][{rng:>16}]"
        if name in file_step_map:
            proto, step, tech = file_step_map[name]
            base = build_fzf_display(proto, step, "", show_protocol=show_proto)
            display_items.append(f"{base} {meta_tag} {name}")
        else:
            display_items.append(f"{meta_tag} {name}")

    selected = fzf_select(
        items=display_items,
        prompt=prompt,
        multi=True,
        preview="",
    )
    if not selected:
        return []

    selected = [s.split()[-1] for s in selected]
    return [str(raw_dir / s) for s in selected]


def _get_results_dir(filepath: str) -> Path:
    """Determine results directory for a given Raman file."""
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


def raman_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("raman")
        return

    sub = args[0]
    sub_args = args[1:]

    if sub == "ls":
        _raman_ls(sub_args)
    elif sub == "info":
        _raman_info_cmd(sub_args)
    elif sub == "plot":
        console.print("[yellow]⚠️  'sci raman plot' is deprecated. Use 'sci plot --technique raman [FLAGS]' instead.[/yellow]")
        _raman_plot(sub_args)
    elif sub == "analyze":
        console.print("[yellow]⚠️  'raman analyze' is deprecated. Use 'analyze --technique raman' instead.[/yellow]")
        _raman_analyze_cmd(sub_args)
    else:
        console.print(f"[yellow]Unknown raman subcommand: {sub}[/yellow]")
        show_command_help("raman")


def _raman_ls(args: list) -> None:
    pos, flags = _parse_flags(args)
    step_name = flags.get("step") or flags.get("n") or ""
    raw_dir = _get_project_raw_dir()

    if not raw_dir:
        console.print("[yellow]No project open. Open a project first.[/yellow]")
        return

    if step_name:
        from science_cli.core.project import get_current_project_path
        proj = get_current_project_path()
        if proj:
            step_dir = _find_step_dir(proj, step_name)
            if step_dir and step_dir.exists():
                files = sorted(step_dir.glob("*"))
                all_files = [f for f in files if f.is_file() and f.name != "results"]
            else:
                console.print(f"[yellow]Step '{step_name}' not found.[/yellow]")
                return
        else:
            console.print("[yellow]No project open.[/yellow]")
            return
    else:
        all_files = _get_raman_files(raw_dir)

    if not all_files:
        console.print("[yellow]No Raman files found.[/yellow]")
        return

    raman_files = [f for f in all_files if "_sers_" not in f.name]
    sers_files = [f for f in all_files if "_sers_" in f.name]

    subtitle = f" — {step_name}" if step_name else ""

    def _render_table(files: list[Path], label: str) -> None:
        if not files:
            return
        table = Table(title=f"{label} Files{subtitle}", border_style="cyan")
        table.add_column("File", style="bold white")
        table.add_column("Size", justify="right", style="dim")
        table.add_column("Accum", style="cyan")
        table.add_column("Acq. Time (s)", style="magenta")
        table.add_column("ND Filter", style="yellow")
        table.add_column("Laser", style="yellow")
        table.add_column("Grating", style="green")
        table.add_column("Range", style="dim")

        for f in files:
            size = f.stat().st_size
            meta = extract_raman_metadata(str(f))
            range_str = _raman_spectral_range(str(f))
            table.add_row(
                f.name,
                f"{size / 1024:.1f}KB" if size >= 1024 else f"{size}B",
                meta.get("accumulations", ""),
                meta.get("acq_time_s", ""),
                meta.get("nd_filter", ""),
                meta.get("laser", ""),
                meta.get("grating", ""),
                range_str,
            )

        console.print(table)

    _render_table(raman_files, "Raman")
    _render_table(sers_files, "SERS")


def _find_step_dir(proj: Path, step_name: str) -> Path | None:
    proto_dir = proj / "protocol"
    if not proto_dir.exists():
        return None
    for proto_subdir in sorted(proto_dir.iterdir()):
        if proto_subdir.is_dir() and not proto_subdir.name.endswith(".yaml"):
            candidate = proto_subdir / step_name
            if candidate.exists():
                return candidate
    return None


def _raman_info_cmd(args: list) -> None:
    pos, flags = _parse_flags(args)
    if not pos:
        files = _raman_fzf_pick_multi("Select Raman file(s) for info")
        if not files:
            return
    else:
        files = [_resolve_file(f) for f in pos]
        files = [f for f in files if f]

    if not files:
        console.print("[red]No valid file(s) found.[/red]")
        return

    for filepath in files:
        _do_raman_info(filepath)


def _do_raman_info(filepath: str) -> None:
    meta = extract_raman_metadata(filepath)

    table = Table(title=f"Raman Metadata: {Path(filepath).name}", border_style="cyan", show_lines=True)
    table.add_column("Field", style="bold white")
    table.add_column("Value", style="dim")

    key_label_map = {
        "instrument": "Instrument",
        "detector": "Detector",
        "laser": "Laser",
        "grating": "Grating",
        "objective": "Objective",
        "nd_filter": "ND Filter",
        "hole": "Hole (µm)",
        "range": "Range",
        "full_time": "Acquisition Time",
        "acq_time_s": "Acq. Time (s)",
        "accumulations": "Accumulations",
        "detector_temperature_c": "Detector Temp (°C)",
        "detector_gain": "Detector Gain",
        "detector_adc": "Detector ADC",
        "x_m": "X (µm)",
        "y_m": "Y (µm)",
        "z_m": "Z (µm)",
        "site": "Site",
        "title": "Title",
        "sample": "Sample",
        "remark": "Remark",
        "date": "Date",
        "acquired": "Acquired",
        "autoexposure": "AutoExposure",
        "autofocus": "Autofocus",
        "autoscann": "AutoScanning",
        "spike_filter": "Spike Filter",
        "delay_time_s": "Delay Time (s)",
        "binning": "Binning",
        "readout_mode": "Readout Mode",
        "denoise": "DeNoise",
        "ics_correction": "ICS Correction",
        "dark_correction": "Dark Correction",
        "inst_process": "Inst. Process",
        "stagexy": "Stage XY",
        "stagez": "Stage Z",
        "ultght": "uLght",
        "project": "Project",
    }

    for key, label in key_label_map.items():
        val = meta.get(key, "")
        if val:
            table.add_row(label, val)

    console.print(table)
    console.print(f"\n[dim]Data rows: loaded on demand via `raman plot {Path(filepath).name}`[/dim]")


def _raman_analyze_cmd(args: list) -> None:
    pos, flags = _parse_flags(args)

    has_pipeline_flags = any(k in flags for k in ("baseline", "denoise", "norm"))

    if not pos:
        files = _raman_fzf_pick_multi("Select Raman file(s) for analysis")
        if not files:
            return
    else:
        files = [_resolve_file(f) for f in pos]
        files = [f for f in files if f]

    if not files:
        console.print("[red]No valid file(s) found.[/red]")
        return

    if "--ai" in args:
        flags = _raman_analyze_ai(files, flags)
    elif not has_pipeline_flags:
        flags = _raman_analyze_interactive(flags)

    results = []
    for filepath in files:
        result = _raman_analyze(filepath, flags)
        if result:
            results.append(result)

    if flags.get("all") and len(results) > 1:
        _raman_analyze_all_plot(results, flags)
    elif flags.get("overlay") and len(results) > 1:
        _raman_analyze_overlay_plot(results, flags)


_AI_FLAG_MAP = {
    "savgol": "savgol",
    "savitzky-golay": "savgol",
    "savgol-window": "savgol-window",
    "savgol_window": "savgol-window",
    "denoise-window": "savgol-window",
    "denoise_window": "savgol-window",
    "savgol-order": "savgol-order",
    "savgol_order": "savgol-order",
    "denoise-order": "savgol-order",
    "denoise_order": "savgol-order",
    "denoise": "denoise",
    "baseline": "baseline",
    "lam": "lam",
    "lambda": "lam",
    "baseline-lambda": "lam",
    "baseline_lambda": "lam",
    "norm": "norm",
    "max": "maxintensity",
    "maxintensity": "maxintensity",
    "minmax": "minmax",
    "auc": "auc",
    "area": "auc",
    "vector": "vector",
    "prominence": "prominence",
    "distance": "distance",
    "plot": "plot",
    "p": "p",
}


def _normalize_ai_flags(rec_flags: dict) -> dict:
    out = {}
    for k, v in rec_flags.items():
        key = k.lstrip("-").lower()
        mapped = _AI_FLAG_MAP.get(key, key)
        val = str(v) if not isinstance(v, bool) else v

        # Handle colon-encoded values like "savgol:7:3" or "arpls:1e5"
        if isinstance(val, str) and ":" in val:
            parts = val.split(":")
            if key in ("denoise", "--denoise"):
                out["denoise"] = parts[0]
                if len(parts) > 1:
                    out["savgol-window"] = parts[1]
                if len(parts) > 2:
                    out["savgol-order"] = parts[2]
                continue
            elif key in ("baseline", "--baseline"):
                out["baseline"] = parts[0]
                if len(parts) > 1:
                    out["lam"] = parts[1]
                continue

        out[mapped] = val
    return out


def _raman_analyze_ai(files: list, flags: dict) -> dict:
    import json, subprocess, tempfile
    from science_cli.core.data_loader import extract_raman_metadata
    from pathlib import Path

    summaries = []
    for f in files:
        meta = extract_raman_metadata(f)
        shift, intensity = _spectrum_from_file(f)
        summaries.append({
            "file": Path(f).name,
            "laser": str(meta.get("laser", "")),
            "nd_filter": str(meta.get("nd_filter", "")),
            "acq_time": str(meta.get("acq_time_s", "")),
            "accums": meta.get("accumulations", 0),
            "data_points": int(len(shift)) if shift is not None else 0,
            "intensity_max": float(np.max(intensity)) if intensity is not None else 0,
        })

    payload = {"files": summaries}

    prompt = (
        "I've attached a JSON file with Raman spectral metadata. "
        "Recommend preprocessing flags for `sci raman analyze`. "
        "Return ONLY a raw JSON object — no markdown, no code fences, no extra text.\n\n"
        'The "flags" field MUST be a JSON object (dictionary), NOT a string. '
        'Example: {"denoise": "savgol", "savgol-window": "7", "baseline": "airpls", '
        '"lam": "10000000", "norm": "vector", "prominence": "100", "plot": true}\n\n'
        "Flag name rules: denoise=savgol|whittaker, savgol-window, savgol-order, "
        "baseline=airpls|asls|arpls|poly|modpoly, "
        "lam (NOT lambda), norm=vector|maxintensity|minmax|auc, prominence, plot."
    )

    sci_dir = str(Path(__file__).resolve().parent.parent.parent)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f, indent=2)
        data_path = f.name

    try:
        proc = subprocess.run(
            ["opencode", "run", "--agent", "sci-raman", "--dir", sci_dir,
             "-m", "opencode-go/mimo-v2.5-pro", "--format", "json",
             prompt, "--file", data_path],
            capture_output=True, text=True, timeout=120,
        )
        out = proc.stdout
        for line in out.splitlines():
            try:
                ev = json.loads(line)
                if ev.get("type") == "text":
                    txt = ev["part"]["text"]
                    # Extract JSON from the response
                    brace_start = txt.find("{")
                    brace_end = txt.rfind("}")
                    if brace_start >= 0 and brace_end > brace_start:
                        rec = json.loads(txt[brace_start:brace_end + 1])
                        break
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        else:
            console.print("[yellow]Could not parse AI response. Using defaults.[/yellow]")
            return flags

        raw_flags = rec.get("flags", {})
        if isinstance(raw_flags, str):
            # Fallback: flags returned as string like "--denoise savgol --baseline airpls"
            _, raw_flags = _parse_flags(raw_flags.split())
        rec_flags = _normalize_ai_flags(raw_flags)
        console.print(f"\n[bold green]AI Recommendation:[/bold green]")
        cmd_display = rec.get("sci_command", "sci raman analyze " + " ".join(f"--{k} {v}" for k, v in rec_flags.items()))
        console.print(f"  Command: [cyan]{cmd_display}[/cyan]")
        for k, v in rec_flags.items():
            flags[k] = v
        reasoning = rec.get("reasoning", "")
        if isinstance(reasoning, dict):
            for step, reason in reasoning.items():
                console.print(f"  [dim]{step}:[/dim] {reason}")
        elif isinstance(reasoning, str) and reasoning:
            for line in reasoning.strip().split("\n"):
                console.print(f"  {line}")
        console.print()

    except subprocess.TimeoutExpired:
        console.print("[yellow]AI agent timed out. Run interactively with `sci raman analyze` (no --ai).[/yellow]")
    except FileNotFoundError:
        console.print("[yellow]opencode not found. Install it or use interactive mode.[/yellow]")
    finally:
        import os
        os.unlink(data_path)

    return flags


def _raman_analyze_interactive(flags: dict) -> dict:
    console.print("\n[bold]Raman Analysis — Interactive Pipeline Builder[/bold]")
    console.print("[dim]Hit Enter for defaults (shown in brackets)[/dim]\n")

    raw = input("  Denoising? [none|savgol|whittaker] (none): ").strip().lower()
    if raw in ("savgol", "whittaker"):
        flags["denoise"] = raw
        if raw == "savgol":
            wl = input("    SavGol window length [7]: ").strip()
            if wl:
                flags["savgol-window"] = wl
            order = input("    SavGol polyorder [3]: ").strip()
            if order:
                flags["savgol-order"] = order
        elif raw == "whittaker":
            lam = input("    Whittaker lambda [1e5]: ").strip()
            if lam:
                flags["lam"] = lam

    raw = input("  Baseline method? [asls|airpls|arpls|poly|modpoly|none] (none): ").strip().lower()
    if raw and raw != "none":
        flags["baseline"] = raw
        lam = input("    Lambda [1e7]: ").strip()
        if lam:
            flags["lam"] = lam
        if raw in ("asls", "iasls"):
            p = input("    Asymmetry p [0.01]: ").strip()
            if p:
                flags["p"] = p

    raw = input("  Normalization? [vector|minmax|maxintensity|auc|none] (none): ").strip().lower()
    if raw and raw != "none":
        flags["norm"] = raw

    raw = input("  Peak prominence [auto \u2014 15% of max intensity]: ").strip()
    if raw:
        flags["prominence"] = raw
    distance = input("  Min peak distance [none]: ").strip()
    if distance:
        flags["distance"] = distance

    raw = input("  Generate plot? [y/N]: ").strip().lower()
    if raw in ("y", "yes"):
        flags["plot"] = True

    console.print()
    return flags


def _raman_plot(args: list) -> None:
    pos, flags = _parse_flags(args)

    overlay_mode = "--overlay" in args
    all_mode = "--all" in args

    if not pos:
        selected_files = _raman_fzf_pick_multi("Select Raman file(s) to plot")
        if not selected_files:
            return

        # Pre-fill flags from raman template + config labels
        all_flags: dict = {}
        from science_cli.theme import template_to_flags
        all_flags.update(template_to_flags("raman"))
        from science_cli.core.config import get_plot_labels
        all_flags.update(get_plot_labels("raman"))

        # Apply active theme defaults
        from science_cli.core.session import get_active_theme
        from science_cli.theme import apply_theme
        apply_theme(get_active_theme())

        if not (all_mode or overlay_mode):
            # Prompt 1: Style / analysis flags with Raman hints
            from science_cli.cli.commands.plot import _technique_hints
            style_hint = _technique_hints("raman").get(
                "plot_style",
                "--type line | --color | --linewidth",
            )
            rprint(f"  [dim]# {style_hint}[/dim]")
            raw_style = input("  Style options (Enter to skip — uses theme defaults): ").strip()
            if raw_style:
                _, style_flags = _parse_flags(raw_style.split())
                all_flags.update(style_flags)

            # Prompt 2: Figure / output flags
            fig_hint = _technique_hints("raman").get(
                "figure",
                "-n spectrum.pdf | --xlabel | --ylabel | --grid | --zoom x1,x2",
            )
            rprint(f"  [dim]# {fig_hint}[/dim]")
            raw_figure = input("  Figure options (Enter to skip — uses theme defaults): ").strip()
            if raw_figure:
                _, figure_flags = _parse_flags(raw_figure.split())
                all_flags.update(figure_flags)

        # Combine with CLI-passed flags
        all_flags.update(flags)
        all_flags["technique"] = "raman"

        resolved = selected_files
    else:
        # Direct files provided via CLI — still apply theme + template defaults
        from science_cli.core.config import get_plot_labels
        from science_cli.core.session import get_active_theme
        from science_cli.theme import apply_theme, template_to_flags
        all_flags: dict = {}
        all_flags.update(template_to_flags("raman"))
        all_flags.update(get_plot_labels("raman"))
        apply_theme(get_active_theme())
        all_flags.update(flags)
        resolved = [_resolve_file(f) for f in pos]
        resolved = [f for f in resolved if f]

    if not resolved:
        console.print("[red]No valid file(s) found.[/red]")
        return

    # Enforce boundaries on all files
    for f in resolved:
        name = Path(f).name.lower()
        if not any(p in name for p in ["_raman", "_sers", "_raman-sers"]):
            console.print(f"[red]Error: File '{Path(f).name}' is not identified as Raman. Enforcing Raman boundaries.[/red]")
            return

    if len(resolved) == 1:
        _do_single_raman_plot(resolved[0], all_flags, auto_save=(all_mode or overlay_mode))
    else:
        # Symmetrically determine overlay vs individual mode
        if not overlay_mode and not all_mode:
            choice = input("  Overlay all (o) or individual plots (i)? [o/i] ").strip().lower()
            if choice == "i":
                all_mode = True
            else:
                overlay_mode = True

        if all_mode:
            for f in resolved:
                _do_single_raman_plot(f, all_flags, auto_save=True)
        else:
            _do_overlay_raman_plot(resolved, all_flags, auto_save=True)


def _do_single_raman_plot(filepath: str, flags: dict, auto_save: bool = False) -> None:
    import matplotlib.pyplot as plt

    # Always enforce active theme before creating figure
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())
    p = Path(filepath)

    try:
        df, info = load_data_file(str(p), technique="raman", device="horiba-usth")
    except Exception:
        df, info = load_data_file(str(p))

    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print(f"[red]Not enough columns in {p.name}.[/red]")
        return

    import pandas as pd
    shift = pd.to_numeric(df[cols[0]], errors="coerce").values
    intensity = pd.to_numeric(df[cols[1]], errors="coerce").values
    mask = ~(np.isnan(shift) | np.isnan(intensity) | (shift <= 0))

    if not mask.any():
        console.print(f"[red]No valid data points in {p.name}.[/red]")
        return

    shift = shift[mask]
    intensity = intensity[mask]

    meta = info.get("raman_metadata", {})
    title = flags.get("title", "")  # only show title if explicitly set
    xlabel = flags.get("xlabel") or "Raman shift (cm⁻¹)"
    ylabel = flags.get("ylabel") or "Intensity (counts)"

    plt.figure()

    # Only override color/linewidth/linestyle if user explicitly passed them;
    # otherwise let the active theme rcParams (prop_cycle, lines.*) control style.
    plot_kwargs: dict = {}
    if flags.get("color"):
        plot_kwargs["color"] = flags["color"]
    if flags.get("linewidth"):
        plot_kwargs["linewidth"] = float(flags["linewidth"])
    if flags.get("linestyle"):
        plot_kwargs["linestyle"] = flags["linestyle"]

    plt.plot(shift, intensity, **plot_kwargs)

    laser = meta.get("laser", "")
    grating = meta.get("grating", "")
    subtitle = f"  [{laser} | {grating}]" if laser and grating else ""

    if title:
        plt.title(f"{title}{subtitle}")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)

    if flags.get("grid"):
        plt.grid(True, alpha=0.3)

    xlim = flags.get("xlim") or flags.get("zoom")
    if xlim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in xlim.split(",")]
            if len(parts) >= 2:
                plt.xlim(parts[0], parts[1])
        except ValueError:
            pass

    ylim = flags.get("ylim")
    if ylim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in ylim.split(",")]
            if len(parts) >= 2:
                plt.ylim(parts[0], parts[1])
        except ValueError:
            pass

    plt.tight_layout()

    out_name = flags.get("name") or flags.get("n")
    if not out_name and auto_save:
        out_name = f"raman_{p.stem}.pdf"

    if out_name:
        out_dir = _get_results_dir(filepath)
        save_path = out_dir / out_name
        if not save_path.suffix:
            save_path = save_path.with_suffix(".pdf")
        plt.savefig(save_path, dpi=int(flags.get("dpi", 300)))
        console.print(f"[green]✓[/green] Saved to {save_path}")
    else:
        plt.show()

    plt.close()


def _do_overlay_raman_plot(files: list, flags: dict, auto_save: bool = False) -> None:
    import matplotlib.pyplot as plt

    # Always enforce active theme before creating figure
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())
    plt.figure()

    title = flags.get("title") or "Raman Overlay Plot"
    xlabel = flags.get("xlabel") or "Raman shift (cm⁻¹)"
    ylabel = flags.get("ylabel") or "Intensity (counts)"
    linewidth = float(flags.get("linewidth", 1.2)) if flags.get("linewidth") else 1.2

    for f in files:
        p = Path(f)
        try:
            df, info = load_data_file(str(p), technique="raman", device="horiba-usth")
        except Exception:
            continue

        cols = info.get("columns", [])
        if len(cols) < 2:
            continue

        import pandas as pd
        shift = pd.to_numeric(df[cols[0]], errors="coerce").values
        intensity = pd.to_numeric(df[cols[1]], errors="coerce").values
        mask = ~(np.isnan(shift) | np.isnan(intensity) | (shift <= 0))

        if not mask.any():
            continue

        plt.plot(shift[mask], intensity[mask], label=p.stem, linewidth=linewidth)

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()

    if flags.get("grid"):
        plt.grid(True, alpha=0.3)

    xlim = flags.get("xlim") or flags.get("zoom")
    if xlim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in xlim.split(",")]
            if len(parts) >= 2:
                plt.xlim(parts[0], parts[1])
        except ValueError:
            pass

    ylim = flags.get("ylim")
    if ylim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in ylim.split(",")]
            if len(parts) >= 2:
                plt.ylim(parts[0], parts[1])
        except ValueError:
            pass

    plt.tight_layout()

    out_name = flags.get("name") or flags.get("n")
    if not out_name and auto_save:
        out_name = "raman_overlay.pdf"

    if out_name:
        out_dir = _get_results_dir(files[0])
        save_path = out_dir / out_name
        if not save_path.suffix:
            save_path = save_path.with_suffix(".pdf")
        plt.savefig(save_path, dpi=int(flags.get("dpi", 300)))
        console.print(f"[green]✓[/green] Saved to {save_path}")
    else:
        plt.show()

    plt.close()


# ── Analyze ──────────────────────────────────────────────────────────


def _raman_spectral_range(filepath: str) -> str:
    """Return formatted spectral range 'min-max cm⁻¹' from data columns."""
    resolved = _resolve_file(filepath)
    if not resolved:
        return ""
    result = _load_raman_data(resolved)
    if result is None:
        return ""
    df, info = result
    cols = info.get("columns", [])
    if len(cols) < 2:
        return ""
    shift = df[cols[0]].values.astype(float)
    if len(shift) < 2:
        return ""
    lo, hi = shift[0], shift[-1]
    return f"{lo:.0f}-{hi:.0f} cm⁻¹"


def _load_raman_data(resolved: str) -> tuple:
    """Load a Horiba Raman file, returning (df, info) robustly."""
    try:
        df, info = load_data_file(str(resolved), technique="raman", device="horiba-usth")
    except Exception:
        df, info = load_data_file(str(resolved))

    cols = info.get("columns", [])
    if len(cols) < 2:
        return None, None

    first_col = cols[0]
    if df[first_col].dtype.kind == "O":
        mask = ~df[first_col].astype(str).str.startswith("#")
        df = df[mask].copy()
        if df.empty:
            return None, None

    return df, info


def _spectrum_from_file(filepath: str) -> tuple:
    """Load a Raman file and return (shift, intensity) arrays."""
    resolved = _resolve_file(filepath)
    if not resolved:
        return None, None

    result = _load_raman_data(resolved)
    if result is None:
        return None, None
    df, info = result

    cols = info.get("columns", [])
    shift = df[cols[0]].values.astype(float)
    intensity = df[cols[1]].values.astype(float)
    mask = ~(np.isnan(shift) | np.isnan(intensity) | (shift <= 0))

    if not mask.any():
        console.print("[red]No valid data points.[/red]")
        return None, None

    return shift[mask], intensity[mask]


def _raman_analyze(filepath: str, flags: dict) -> None:
    import ramanspy as rp

    resolved = _resolve_file(filepath)
    if not resolved:
        console.print(f"[red]File not found: {filepath}[/red]")
        return

    p = Path(resolved)
    shift, intensity = _spectrum_from_file(resolved)
    if shift is None:
        return

    raw_intensity = intensity.copy()
    meta = extract_raman_metadata(resolved)

    console.print(f"\n[bold]Raman Analysis: {p.name}[/bold]")
    console.print(f"  Data points: {len(shift)}")

    def _fk(key: str, default: str = "") -> str:
        return flags.get(key, flags.get(key.replace("-", "_"), default))

    # Build and apply RamanSPy preprocessing pipeline step by step
    applied = rp.Spectrum(intensity, spectral_axis=shift)
    baseline_curve = None

    # 1. Denoising
    denoise = flags.get("denoise", "")
    if denoise == "savgol":
        wl = int(_fk("savgol-window", "7"))
        order = int(_fk("savgol-order", "3"))
        step = rp.preprocessing.denoise.SavGol(window_length=wl, polyorder=order)
        applied = step.apply(applied)
        console.print(f"  Denoising: Savitzky-Golay (window={wl}, polyorder={order})")
    elif denoise == "whittaker":
        lam = float(flags.get("lam", 1e5))
        step = rp.preprocessing.denoise.Whittaker(lam=lam)
        applied = step.apply(applied)
        console.print(f"  Denoising: Whittaker (lam={lam:.0e})")

    # 2. Baseline correction
    baseline_method = flags.get("baseline", "")
    if baseline_method:
        lam = float(flags.get("lam", 1e7))
        p_asym = float(flags.get("p", 0.01))

        baseline_map = {
            "asls":    rp.preprocessing.baseline.ASLS(lam=lam, p=p_asym),
            "iasls":   rp.preprocessing.baseline.IASLS(lam=lam, p=p_asym),
            "airpls":  rp.preprocessing.baseline.AIRPLS(lam=lam),
            "arpls":   rp.preprocessing.baseline.ARPLS(lam=lam),
            "iarpls":  rp.preprocessing.baseline.IARPLS(lam=lam),
            "poly":    rp.preprocessing.baseline.Poly(),
            "modpoly": rp.preprocessing.baseline.ModPoly(),
        }

        method = baseline_map.get(baseline_method)
        if method is None:
            console.print(f"[yellow]Unknown baseline method '{baseline_method}'. Using ASLS.[/yellow]")
            method = baseline_map["asls"]

        before = np.ravel(applied.spectral_data)
        applied = method.apply(applied)
        baseline_curve = before - np.ravel(applied.spectral_data)
        console.print(f"  Baseline: {baseline_method.upper()} (lam={lam:.0e}{', p=' + str(p_asym) if baseline_method in ('asls','iasls') else ''})")

    # 3. Normalization
    norm_method = flags.get("norm", "")
    if norm_method:
        norm_map = {
            "vector":       rp.preprocessing.normalise.Vector(),
            "minmax":       rp.preprocessing.normalise.MinMax(),
            "maxintensity": rp.preprocessing.normalise.MaxIntensity(),
            "auc":          rp.preprocessing.normalise.AUC(),
            "area":         rp.preprocessing.normalise.AUC(),
        }
        method = norm_map.get(norm_method)
        if method is None:
            console.print(f"[yellow]Unknown norm method '{norm_method}'. Using max-intensity.[/yellow]")
            method = norm_map["maxintensity"]

        applied = method.apply(applied)
        console.print(f"  Normalization: {norm_method}")

    spec = applied

    # 4. Peak finding
    max_int = float(np.max(spec.spectral_data)) if len(spec.spectral_data) > 0 else 1.0
    default_prom = max(0.15 * max_int, 1.0)
    prominence = float(flags.get("prominence", default_prom))
    distance = flags.get("distance")
    height = flags.get("height")
    width = flags.get("width")

    peak_kwargs: dict = {"prominence": prominence}
    if distance is not None:
        peak_kwargs["distance"] = int(distance)
    if height is not None:
        peak_kwargs["height"] = float(height)
    if width is not None:
        peak_kwargs["width"] = float(width)

    peaks, props = spec.peaks(**peak_kwargs)
    normalized = bool(norm_method)

    from scipy.signal import peak_widths
    if len(peaks) > 0:
        try:
            widths_result = peak_widths(spec.spectral_data, peaks, rel_height=0.5)
            left_ips = widths_result[2]
            right_ips = widths_result[3]
            fwhms = spec.spectral_axis[np.minimum(np.round(right_ips).astype(int), len(spec.spectral_axis) - 1)] \
                  - spec.spectral_axis[np.minimum(np.round(left_ips).astype(int), len(spec.spectral_axis) - 1)]
        except Exception:
            fwhms = np.full(len(peaks), np.nan)

        peak_shifts = spec.spectral_axis[peaks]
        peak_intensities = spec.spectral_data[peaks]
        peak_prominences = props.get("prominences", np.full(len(peaks), np.nan))
    else:
        console.print(f"  [yellow]No peaks found with prominence={prominence}. Try --prominence <lower>[/yellow]")
        peak_shifts = np.array([])
        peak_intensities = np.array([])
        peak_prominences = np.array([])
        fwhms = np.array([])

    if len(peaks) > 0:
        peak_table = Table(title=f"Detected Peaks ({len(peaks)} found)", border_style="green")
        peak_table.add_column("#", style="dim", justify="right")
        peak_table.add_column("Shift (cm⁻¹)", style="bold cyan", justify="right")
        peak_table.add_column("Intensity (a.u.)" if normalized else "Intensity (counts)", justify="right")
        peak_table.add_column("Prominence", justify="right")
        peak_table.add_column("FWHM (cm⁻¹)", justify="right")

        for i, (s, v, prom, fw) in enumerate(zip(peak_shifts, peak_intensities, peak_prominences, fwhms)):
            fw_str = f"{fw:.1f}" if not np.isnan(fw) else "\u2014"
            peak_table.add_row(
                str(i + 1),
                f"{s:.1f}",
                f"{v:.4e}" if not normalized else f"{v:.4f}",
                f"{prom:.1f}",
                fw_str,
            )

        console.print(peak_table)

    # 5. Save CSV outputs
    out_dir = _get_results_dir(resolved)
    prefix = flags.get("name") or p.stem

    saved = []
    import pandas as pd

    if len(peaks) > 0:
        peaks_df = pd.DataFrame({
            "peak_center(cm⁻¹)": peak_shifts,
            "intensity(counts)" if not normalized else "intensity(a.u.)": peak_intensities,
            "prominence": peak_prominences,
            "fwhm(cm⁻¹)": fwhms,
        })
        peaks_csv = out_dir / f"{prefix}_peaks.csv"
        peaks_df.to_csv(peaks_csv, index=False)
        saved.append(peaks_csv)

    if baseline_method:
        processed_df = pd.DataFrame({
            "shift(cm⁻¹)": spec.spectral_axis,
            "intensity": spec.spectral_data,
        })
        processed_csv = out_dir / f"{prefix}_processed.csv"
        processed_df.to_csv(processed_csv, index=False)
        saved.append(processed_csv)

    if saved:
        console.print("\n[bold green]Saved:[/bold green]")
        for csv_path in saved:
            console.print(f"  \u2713 {csv_path}")

    # 6. Save text report (automatic)
    _raman_analyze_save_report(out_dir, prefix, p, meta, flags, peaks, peak_shifts, peak_intensities, peak_prominences, fwhms, normalized, denoise, baseline_method, norm_method)

    # 7. Enhanced analysis plot (optional)
    if flags.get("plot"):
        _raman_analyze_plot_enhanced(shift, raw_intensity, baseline_curve, spec, peaks, flags, p, normalized, baseline_method)

    # Console summary
    if len(peaks) > 0:
        console.print(f"\n  [bold]Summary:[/bold] {len(peaks)} peaks detected")
        major = [s for s in peak_shifts if s > 500]
        if major:
            unit = "cm\u207b\u00b9"
            labels = [f"{s:.0f} {unit}" for s in major[:5]]
            console.print(f"  Major bands: {', '.join(labels)}")
            if len(major) > 5:
                console.print(f"    ... and {len(major) - 5} more")

    return {
        "name": p.stem,
        "shift": spec.spectral_axis,
        "corrected": spec.spectral_data,
        "raw_intensity": raw_intensity,
        "baseline_curve": baseline_curve,
        "peaks": peaks,
        "normalized": normalized,
    }


def _raman_analyze_save_report(out_dir: Path, prefix: str, p: Path, meta: dict, flags: dict,
                               peaks, peak_shifts, peak_intensities, peak_prominences, fwhms,
                               normalized: bool, denoise: str, baseline_method: str, norm_method: str) -> None:
    sep = "=" * 80
    sub_sep = "-" * 80

    lines = []
    lines.append(sep)
    lines.append("  RAMAN ANALYSIS REPORT")
    lines.append(sep)
    lines.append("")

    def _fk(key: str, default: str = "") -> str:
        return flags.get(key, flags.get(key.replace("-", "_"), default))

    lines.append(f"File:        {p.name}")
    lines.append(f"Laser:       {meta.get('laser', 'N/A')}")
    lines.append(f"ND Filter:   {meta.get('nd_filter', 'N/A')}")
    lines.append(f"Acq. Time:   {meta.get('acq_time_s', 'N/A')} s")
    lines.append(f"Accums:      {meta.get('accumulations', 'N/A')}")
    lines.append("")

    lines.append(sub_sep)
    lines.append("  PIPELINE")
    lines.append(sub_sep)

    if denoise == "savgol":
        wl = _fk("savgol-window", "7")
        order = _fk("savgol-order", "3")
        lines.append(f"Denoising:      Savitzky-Golay (window={wl}, polyorder={order})")
    elif denoise == "whittaker":
        lam = flags.get("lam", "1e5")
        lines.append(f"Denoising:      Whittaker (lam={lam})")
    else:
        lines.append("Denoising:      None")

    if baseline_method:
        lam = flags.get("lam", "1e7")
        lines.append(f"Baseline:       {baseline_method.upper()} (lam={lam})")
    else:
        lines.append("Baseline:       None")

    if norm_method:
        lines.append(f"Normalization:  {norm_method.capitalize()}")
    else:
        lines.append("Normalization:  None")

    lines.append("")
    lines.append(sub_sep)
    lines.append("  DETECTED PEAKS")
    lines.append(sub_sep)
    lines.append("")

    n_peaks = len(peaks)
    if n_peaks > 0:
        intensity_label = "Intensity (a.u.)" if normalized else "Intensity (counts)"
        header = f"  {'#':>3}  {'Shift (cm⁻¹)':>13}  {intensity_label:>13}  {'Prominence':>12}  {'FWHM (cm⁻¹)':>12}"
        lines.append(header)
        lines.append(f" {'---':>3}  {'------------':>13}  {'------------':>13}  {'----------':>12}  {'-----------':>12}")
        for i, (s, v, prom, fw) in enumerate(zip(peak_shifts, peak_intensities, peak_prominences, fwhms)):
            fw_str = f"{fw:.1f}" if not np.isnan(fw) else "---"
            v_str = f"{v:.4e}" if not normalized else f"{v:.4f}"
            lines.append(f"  {i+1:>3}  {s:>13.1f}  {v_str:>13}  {prom:>12.1f}  {fw_str:>12}")
    else:
        lines.append("  No peaks detected.")
    lines.append("")

    lines.append(sub_sep)
    lines.append("  SUMMARY")
    lines.append(sub_sep)
    lines.append("")

    lines.append(f"Total peaks:        {n_peaks}")
    if n_peaks > 0:
        max_int = float(np.max(peak_intensities))
        lines.append(f"Max intensity:      {max_int:.3f}")
        major = [s for s in peak_shifts if s > 500]
        if len(major) > 0:
            labels = [f"{s:.0f} cm\u207b\u00b9" for s in major[:5]]
            lines.append(f"Major bands:        {', '.join(labels)}")

    report_path = out_dir / f"{prefix}_report.txt"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    console.print(f"  \u2713 Report: {report_path}")


def _raman_analyze_plot_enhanced(shift, raw_intensity, baseline_curve, spec, peaks, flags, p, normalized, baseline_method):
    import matplotlib.pyplot as plt

    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())

    fig, ax = plt.subplots(figsize=(8, 3.5))

    ax.plot(shift, raw_intensity, color="gray", lw=0.5, alpha=0.4, label="Raw")

    if baseline_curve is not None and baseline_method:
        ax.plot(shift, baseline_curve, color="#FF8C00", lw=0.8, linestyle="--",
                label=f"Baseline ({baseline_method})")

    label = "Corrected + Normalized" if normalized else "Corrected"
    ax.plot(spec.spectral_axis, spec.spectral_data, color="black", lw=1.0, label=label)

    if len(peaks) > 0:
        ax.scatter(spec.spectral_axis[peaks], spec.spectral_data[peaks],
                   color="red", s=25, zorder=5, label=f"Peaks ({len(peaks)})")

    if len(peaks) > 0:
        peak_shifts = spec.spectral_axis[peaks]
        annotated = []
        for i, s in enumerate(peak_shifts):
            if not annotated or abs(s - annotated[-1]) > 15:
                y = float(spec.spectral_data[peaks][i])
                ax.annotate(f"{s:.0f} cm\u207b\u00b9", xy=(s, y), xytext=(0, 8),
                            textcoords="offset points", rotation=45, fontsize=7,
                            color="red", ha="center")
                annotated.append(s)

    shift_unit = "cm\u207b\u00b9"
    ylabel = "Intensity (a.u.)" if normalized else "Intensity (counts)"
    ax.set_xlabel(f"Raman shift ({shift_unit})")
    ax.set_ylabel(ylabel)
    ax.set_title(p.stem)
    ax.legend(frameon=False, fontsize=7)

    out_dir = _get_results_dir(str(p))
    pdf_path = out_dir / f"{p.stem}_analysis.pdf"
    fig.savefig(pdf_path, bbox_inches="tight")
    console.print(f"  \u2713 Plot: {pdf_path}")
    plt.close(fig)


def _raman_analyze_overlay_plot(results: list, flags: dict) -> None:
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())
    fig, ax = plt.subplots(figsize=(8, 3.5))

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
              "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

    for i, r in enumerate(results):
        color = colors[i % len(colors)]
        ax.plot(r["shift"], r["corrected"], color=color, lw=1.0, label=r["name"])

    ax.set_xlabel("Raman shift (cm\u207b\u00b9)")
    ylabel = "Intensity (a.u.)" if any(r["normalized"] for r in results) else "Intensity (counts)"
    ax.set_ylabel(ylabel)
    title = flags.get("title") or "Raman Overlay — " + ", ".join(r["name"] for r in results[:3])
    if len(results) > 3:
        title += f" (+{len(results) - 3} more)"
    ax.set_title(title)
    if not flags.get("no-legend"):
        ax.legend(frameon=False, fontsize=7)

    xlim = flags.get("xlim") or flags.get("zoom")
    if xlim:
        try:
            parts = [float(v.strip().replace(",", ".")) for v in xlim.split(",")]
            if len(parts) >= 2:
                ax.set_xlim(parts[0], parts[1])
        except ValueError:
            pass

    out_dir = _get_results_dir(".")
    pdf_path = out_dir / "raman_analyze_overlay.pdf"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(pdf_path.with_suffix(".png"), bbox_inches="tight", dpi=150)
    console.print(f"  \u2713 Overlay plot: {pdf_path}")
    plt.close(fig)


def _raman_analyze_all_plot(results: list, flags: dict) -> None:
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme

    apply_theme(get_active_theme())
    n = len(results)
    fig, axes = plt.subplots(n, 1, figsize=(8, 2.5 * n), sharex=True)
    if n == 1:
        axes = [axes]

    for i, (ax, r) in enumerate(zip(axes, results)):
        ax.plot(r["shift"], r["corrected"], color="black", lw=1.0)
        ax.set_ylabel("Intensity (a.u.)" if r["normalized"] else "Intensity (counts)")
        ax.set_title(r["name"], fontsize=9)
        if r.get("baseline_curve") is not None:
            ax.plot(r["shift"], r["baseline_curve"], color="#FF8C00", lw=0.6,
                    linestyle="--", alpha=0.6)
        if len(r.get("peaks", [])) > 0:
            ax.scatter(r["shift"][r["peaks"]], r["corrected"][r["peaks"]],
                       color="red", s=15, zorder=5)

    axes[-1].set_xlabel("Raman shift (cm\u207b\u00b9)")

    title = flags.get("title") or "Raman Analysis — All Spectra"
    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    out_dir = _get_results_dir(".")
    pdf_path = out_dir / "raman_analyze_all.pdf"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(pdf_path.with_suffix(".png"), bbox_inches="tight", dpi=150)
    console.print(f"  \u2713 All plot: {pdf_path}")
    plt.close(fig)

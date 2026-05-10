"""analyze command handler — analysis only (no plotting).

Uses the ExtensionRegistry for analyzer dispatch and ColumnMap for
column identification. No direct imports from extension packages at
module level — all extension-specific types are imported lazily.
"""

from pathlib import Path
import yaml
from rich.console import Console
from rich import print as rprint

from science_cli.cli.help import show_command_help
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


def _detect_technique(filename: str) -> str:
    from science_cli.core.technique import detect_technique
    t = detect_technique(filename)
    return t.lower() if t else ""


def _get_results_dir(filepath: str) -> Path:
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


def _resolve_columns(df: "pd.DataFrame", technique: str) -> tuple:
    """Resolve x, y columns and labels using the registry ColumnMap.

    Returns: (xcol, ycol, xlabel, ylabel, extras_dict)
    """
    import numpy as np

    xcol, ycol = "", ""
    xlabel, ylabel = "", ""
    extras: dict = {}

    # 1. Try extension registry ColumnMap
    if technique:
        try:
            from science_cli.extensions import get_registry
            registry = get_registry()
            cm = registry.column_maps.get(technique)
            if cm is not None:
                xcol, ycol, xlabel, ylabel, extras = cm.resolve(list(df.columns))
        except ImportError:
            pass

    # 2. Fallback: first two numeric columns
    if not xcol or not ycol:
        numeric = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c not in ("Index", "index")
        ]
        if len(numeric) >= 2:
            xcol, ycol = numeric[0], numeric[1]

    return xcol, ycol, xlabel or xcol, ylabel or ycol, extras


def analyze_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("analyze")
        return

    if args[0] == "-f":
        files_str = args[1] if len(args) > 1 else ""
        rest = args[2:] if len(args) > 2 else []
        files = [f.strip() for f in files_str.split(",") if f.strip()]
        _analyze_direct(files, rest)
    else:
        console.print("[yellow]Usage: analyze -f <file> [options][/yellow]")


def _analyze_direct(files: list, rest_args: list) -> None:
    _, flags = _parse_flags(rest_args)

    if not files:
        console.print("[yellow]No files specified.[/yellow]")
        return

    filepath = _resolve_file(files[0])
    if not filepath:
        console.print(f"[red]File not found: {files[0]}[/red]")
        return

    tech = _detect_technique(Path(filepath).name)

    # Get analyzer from registry
    analyzer = None
    try:
        from science_cli.extensions import discover_extensions
        registry = discover_extensions()
        analyzer = registry.analyzers.get(tech)
    except ImportError:
        pass

    if analyzer is None:
        console.print(f"[yellow]No analyzer registered for technique: {tech}[/yellow]")
        console.print("[dim]Try: sci techniques  to see available techniques.[/dim]")
        return

    # Dispatch to per-technique handler (handles model construction + analysis + display)
    if tech.startswith("ec-"):
        _analyze_electrochem(filepath, flags, tech, analyzer)
    elif tech.startswith("iv-"):
        _analyze_iv(filepath, flags, tech, analyzer)
    elif tech.startswith("mem-"):
        _analyze_memristor(filepath, flags, tech, analyzer)
    else:
        _analyze_generic(filepath, flags, tech, analyzer)

    # Sweep metadata: detect and store in protocol YAML
    _save_sweep_metadata(filepath)


# ── Per-technique-family handlers ──────────────────────────────────────


def _analyze_electrochem(
    filepath: str, flags: dict, tech: str, analyzer
) -> None:
    """Analyze electrochem data (CV, CA, EIS) via registry analyzer."""
    from science_cli.core.data_loader import load_data_file
    import numpy as np

    df, info = load_data_file(filepath)
    xcol, ycol, xlabel, ylabel, extras = _resolve_columns(df, tech)

    if not xcol or not ycol:
        console.print("[red]Could not determine columns for this technique.[/red]")
        return

    x = np.asarray(df[xcol].values, dtype=float)
    y = np.asarray(df[ycol].values, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    console.print(f"\n[bold]{tech.upper()} Analysis: {Path(filepath).name}[/bold]")

    # Construct domain model and run analysis (lazy imports of extension types)
    if tech == "ec-cv":
        from science_electrochem.models import CVData
        data = CVData(potential=x, current=y, scan_rate=0.0)
        result = analyzer(data, {})
        _display_cv_results(result, flags)
        param_summary = {"peaks": len(result.get("peaks", {}).get("anodic_peaks", [])),
                         "charge": flags.get("charge", False)}
        _save_analysis_manifest(filepath, "CV", param_summary)

    elif tech == "ec-ca":
        from science_electrochem.models import CAData
        data = CAData(time=x, current=y)
        result = analyzer(data, {"fit": flags.get("fit", True), "steady_state": True})
        _display_ca_results(result)
        _save_analysis_manifest(filepath, "CA", {"fit": flags.get("fit", False)})

    elif tech == "ec-eis":
        from science_electrochem.models import EISData
        # EIS needs frequency + complex impedance
        z_col = extras.get("z_imag", "")
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
        circuit = flags.get("circuit", "RRC")
        options = {"circuit_model": circuit, "kk": flags.get("kk", False)}
        result = analyzer(data, options)
        _display_eis_results(result, circuit, flags)
        _save_analysis_manifest(
            filepath, "EIS", {"circuit": circuit, "kk": flags.get("kk", False)}
        )


def _analyze_iv(
    filepath: str, flags: dict, tech: str, analyzer
) -> None:
    """Analyze IV data (sweep, breakdown, leakage) via registry analyzer."""
    from science_cli.core.data_loader import load_data_file
    import numpy as np

    df, info = load_data_file(filepath)
    xcol, ycol, xlabel, ylabel, _extras = _resolve_columns(df, tech)

    if not xcol or not ycol:
        console.print("[red]Could not determine columns for IV analysis.[/red]")
        return

    x = np.asarray(df[xcol].values, dtype=float)
    y = np.asarray(df[ycol].values, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    console.print(f"\n[bold]{tech.upper()} Analysis: {Path(filepath).name}[/bold]")

    try:
        result = analyzer(x, y)
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        return

    if not isinstance(result, dict):
        return

    if "resistance" in result and result["resistance"] is not None:
        console.print(f"  Resistance: {result['resistance']:.2e} Ω  (R²={result.get('r_squared', 0):.4f})")
    if "breakdown_voltage" in result and result["breakdown_voltage"] is not None:
        console.print(f"  V_bd: {result['breakdown_voltage']:.4f} V  @ {result['breakdown_current']:.2e} A")
    if "on_off_ratio" in result and result["on_off_ratio"] is not None:
        console.print(f"  On/Off ratio: {result['on_off_ratio']:.2f}")

    _save_analysis_manifest(filepath, tech.upper(), {
        k: v for k, v in result.items()
        if isinstance(v, (int, float, str, bool))
    })


def _analyze_memristor(
    filepath: str, flags: dict, tech: str, analyzer
) -> None:
    """Analyze memristor data (endurance, retention, switching) via registry."""
    from science_cli.core.data_loader import load_data_file

    df, info = load_data_file(filepath)
    console.print(f"\n[bold]{tech.upper()} Analysis: {Path(filepath).name}[/bold]")

    try:
        result = analyzer(df)
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        return

    if isinstance(result, dict):
        for k, v in result.items():
            if isinstance(v, (int, float, str)):
                console.print(f"  {k}: {v}")
            elif isinstance(v, (list, dict)):
                console.print(f"  {k}: {v!r}")

    _save_analysis_manifest(filepath, tech.upper(),
                            {"analyzer": tech} if not isinstance(result, dict) else {})


def _analyze_generic(
    filepath: str, flags: dict, tech: str, analyzer
) -> None:
    """Generic analysis for unknown technique families."""
    from science_cli.core.data_loader import load_data_file
    import numpy as np

    df, info = load_data_file(filepath)
    xcol, ycol, xlabel, ylabel, _extras = _resolve_columns(df, tech)

    console.print(f"\n[bold]{tech.upper()} Analysis: {Path(filepath).name}[/bold]")

    if xcol and ycol:
        x = np.asarray(df[xcol].values, dtype=float)
        y = np.asarray(df[ycol].values, dtype=float)
        mask = ~(np.isnan(x) | np.isnan(y))
        try:
            result = analyzer(x[mask], y[mask])
        except Exception:
            try:
                result = analyzer(df)
            except Exception as e:
                console.print(f"[red]Analysis failed: {e}[/red]")
                return
        if isinstance(result, dict):
            for k, v in result.items():
                if isinstance(v, (int, float, str)):
                    console.print(f"  {k}: {v}")

    _save_analysis_manifest(filepath, tech.upper(), {})


# ── Result display helpers ─────────────────────────────────────────────


def _display_cv_results(result: dict, flags: dict) -> None:
    """Display CV peak analysis results."""
    peaks = result.get("peaks", {})
    if not peaks:
        console.print("  [dim]No peaks detected.[/dim]")
        return

    console.print(f"  Anodic peaks: {peaks.get('n_anodic', 0)}")
    for pk in peaks.get("anodic_peaks", []):
        console.print(f"    E_pa={pk.get('potential', 0):.4f}V  I_pa={pk.get('current', 0):.4e}A")
    console.print(f"  Cathodic peaks: {peaks.get('n_cathodic', 0)}")
    for pk in peaks.get("cathodic_peaks", []):
        console.print(f"    E_pc={pk.get('potential', 0):.4f}V  I_pc={pk.get('current', 0):.4e}A")
    if "average_peak_separation" in peaks:
        console.print(f"  ΔE_p = {peaks['average_peak_separation']:.4f}V")

    if flags.get("charge") and "charge" in result:
        charge = result["charge"]
        console.print(f"  Charge: {charge.get('total_charge', 0):.4e}C")
        console.print(f"  Anodic: {charge.get('anodic_charge', 0):.4e}C  "
                      f"Cathodic: {charge.get('cathodic_charge', 0):.4e}C")


def _display_ca_results(result: dict) -> None:
    """Display CA (Cottrell + steady-state) results."""
    if "cottrell" in result:
        cr = result["cottrell"]
        if "error" not in cr:
            console.print(f"  Cottrell slope: {cr.get('slope', 0):.4e} A·√s  R²={cr.get('r_squared', 0):.4f}")
        else:
            console.print(f"  [red]Cottrell fit failed: {cr['error']}[/red]")
    if "steady_state" in result:
        ss = result["steady_state"]
        console.print(f"  Steady state: {ss.get('steady_state_current', 0):.4e}A")


def _display_eis_results(result: dict, circuit: str, flags: dict) -> None:
    """Display EIS (circuit fit + KK) results."""
    if flags.get("kk") and "kk" in result:
        kk = result["kk"]
        status = "✓ passed" if kk.get("passes") else "✗ failed"
        console.print(f"  KK test: {status}  (score={kk.get('consistency_score', 0):.3f})")

    fit = result.get("circuit_fit", {})
    if not fit:
        return

    console.print(f"  Circuit fit: {fit.get('circuit', circuit)}")
    if "error" in fit:
        console.print(f"  [red]Fit failed: {fit['error']}[/red]")
    else:
        for n, v in zip(fit.get("parameter_names", []), fit.get("fitted_params", [])):
            console.print(f"    {n}: {v:.4e}")
        console.print(f"    R²: {fit.get('r_squared', 0):.4f}")


# ── Utilities ──────────────────────────────────────────────────────────


def _save_analysis_manifest(filepath: str, technique: str, results: dict) -> None:
    """Emit analysis manifest for reproducibility."""
    out_dir = _get_results_dir(filepath)
    from science_cli.core.manifest import emit_manifest
    from science_cli.core.project import get_current_project_path
    emit_manifest(
        output_dir=out_dir,
        command=f"analyze {filepath}",
        source_files=[filepath],
        output_files=[],
        technique=technique,
        parameters=results,
        project=get_current_project_path().name if get_current_project_path() else "",
    )
    console.print(f"\n[dim]Results saved to {out_dir}/manifest.json[/dim]")


def _save_sweep_metadata(filepath: str) -> None:
    """Extract and save sweep metadata to protocol YAML."""
    from science_cli.core.sweep_metadata import extract_sweep_from_file, update_protocol_with_sweep
    from science_cli.core.session import load_session
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
    sess = load_session()
    pname = sess.get("last_protocol", "")
    proj = get_current_project_path()
    if not (pname and proj):
        return

    paths = ProjectPaths(proj)
    yaml_path = paths.protocol_yaml(pname)
    if not yaml_path.exists():
        return

    fname = Path(filepath).name
    with open(yaml_path) as f:
        proto = yaml.safe_load(f) or {}

    for s in proto.get("steps", []):
        step_files = s.get("files", [])
        norm = [e["file"] if isinstance(e, dict) else e for e in step_files]
        if fname not in norm:
            continue
        segs = extract_sweep_from_file(filepath)
        if segs:
            update_protocol_with_sweep(yaml_path, s["name"], fname, segs)
            ndirs = ", ".join(sg["direction"] for sg in segs)
            console.print(
                f"  [dim]sweep: {len(segs)} seg [{ndirs}] "
                f"@ {segs[0]['sweep_rate_v_s']} V/s[/dim]"
            )
        break

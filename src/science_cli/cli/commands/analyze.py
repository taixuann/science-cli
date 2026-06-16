"""analyze command handler — analysis only (no plotting)."""

from pathlib import Path

import yaml
from rich.console import Console

from science_cli.cli.help import show_command_help
from science_cli.core.file_utils import is_flag

console = Console()

TECHNIQUE_ANALYZERS = {
    "iv-sweep": "_analyze_iv",
    "iv-breakdown": "_analyze_iv",
    "iv-leakage": "_analyze_iv",
    "pulse-endurance": "_analyze_pulse_endurance",
    "pulse-retention": "_analyze_pulse_retention",
    "pulse-stp": "_analyze_pulse_stp",
    "pulse-ppf": "_analyze_pulse_ppf",
    "ec-cv": "_analyze_cv",
    "ec-ca": "_analyze_ca",
    "ec-eis": "_analyze_eis",
    "raman": "_analyze_raman",
    "uv-vis": "_analyze_uv_vis",
    "afm-gwy": "_analyze_afm",
}

ANALYZE_TECHNIQUE_FLAGS: dict[str, list[dict]] = {
    "iv-sweep": [
        {"name": "--yaml", "action": "store_true", "help": "Output analysis YAML to results/"},
        {"name": "--vset-only", "action": "store_true", "help": "Volatile mode: V_set only, no V_reset"},
        {"name": "--compliance", "type": float, "help": "Compliance current (A)"},
    ],
    "pulse-stp": [
        {"name": "--yaml", "action": "store_true", "help": "Output analysis YAML"},
        {"name": "--fit-model", "type": str, "help": "Decay fit model: biexponential|stretched"},
    ],
    "pulse-ppf": [
        {"name": "--yaml", "action": "store_true", "help": "Output analysis YAML"},
        {"name": "--intervals", "type": str, "help": "Comma-separated intervals (ms): 10,50,100"},
    ],
    "raman": [
        {"name": "--yaml", "action": "store_true", "help": "Output analysis YAML"},
        {"name": "--peaks", "action": "store_true", "help": "Find and report peaks"},
        {"name": "--baseline", "type": str, "help": "Baseline method: poly|asls|airpls"},
    ],
    "uv-vis": [
        {"name": "--yaml", "action": "store_true", "help": "Output analysis YAML"},
        {"name": "--bandgap", "action": "store_true", "help": "Compute Tauc bandgap"},
    ],
    "afm": [
        {"name": "--yaml", "action": "store_true", "help": "Output analysis YAML"},
        {"name": "--roughness", "action": "store_true", "help": "Compute Sa/Sq roughness"},
    ],
}


def _detect_device_type_analyze(
    study_name: str | None = None,
    flags: dict | None = None,
) -> str | None:
    """Lightweight device-type detection for the analyze dispatch chain.

    Resolution order (simplified — no protocol YAML lookup for analyze):
        1. ``flags["device-type"]`` or ``flags["dt"]`` — explicit CLI override
        2. Reverse lookup — which device_type lists this study?

    Args:
        study_name: Study name in "technique:study-name" format or legacy name.
        flags: Parsed CLI flags dict (may contain ``device-type`` / ``dt``).

    Returns:
        Device type slug (e.g. ``"volatile-memristor"``) or ``None``.
    """
    # 1. Explicit CLI flag
    if flags:
        dt = flags.get("device-type") or flags.get("dt", "")
        if dt:
            return str(dt)

    # 2. Reverse lookup: which device types include this study?
    if study_name:
        try:
            from science_cli.core.config_defaults import _DEVICE_TYPES
            matching: list[str] = []
            for dt_slug, dt_cfg in _DEVICE_TYPES.items():
                if study_name in dt_cfg.get("studies", []):
                    matching.append(dt_slug)
            if len(matching) == 1:
                return matching[0]
        except Exception:
            pass

    return None


def _parse_flags(args: list) -> tuple:
    positional = []
    flags = {}
    i = 0
    while i < len(args):
        a = args[i]
        if is_flag(a):
            key = a.lstrip("-")
            if key == "yaml":
                flags[key] = True
                i += 1
            elif i + 1 < len(args) and not is_flag(args[i + 1]):
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


from science_cli.core.device_resolver import resolve_device as _resolve_device


def _get_results_dir(filepath: str) -> Path:
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


def analyze_handler(args: list) -> None:
    if not args or args[0] in ("--help", "-h"):
        show_command_help("analyze")
        return

    positional, flags = _parse_flags(args)
    explicit_technique = flags.get("t") or flags.get("technique", "")
    explicit_study = flags.get("s") or flags.get("study", "")

    # If study flag given and technique is not, derive technique from study
    if explicit_study and not explicit_technique:
        from science_cli.core.config import resolve_technique_from_study
        explicit_technique = resolve_technique_from_study(explicit_study)
        console.print(f"  [dim]Derived technique '{explicit_technique}' from study '{explicit_study}'[/dim]")

    # Detect device_type from flags or reverse study lookup
    device_type = _detect_device_type_analyze(
        study_name=explicit_study,
        flags=flags,
    )

    if explicit_technique:
        warnings = _validate_analyze_flags(flags, technique=explicit_technique)
        for w in warnings:
            console.print(f"[yellow]Warning:[/yellow] {w}")
        _analyze_with_technique(
            explicit_technique, flags,
            study_name=explicit_study, device_type=device_type,
        )
        return

    # Check if args contain a file path (no fzf needed)
    if positional:
        _analyze_direct(positional, args)
        return

    # Default to fzf file selection, then analyze
    from science_cli.core.fzf_utils import fzf_select
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

    item_names = [f.name for f in files]
    selected = fzf_select(item_names, prompt="Select a file to analyze:", multi=False)
    if not selected:
        console.print("[yellow]No file selected.[/yellow]")
        return

    filepath = str(raw_dir / selected[0])
    _analyze_direct([filepath], args)


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

    if tech == "cv":
        _analyze_cv(filepath, flags)
    elif tech == "ca":
        _analyze_ca(filepath, flags)
    elif tech in ("eis", "ec-eis"):
        _analyze_eis(filepath, flags)
    elif tech in ("iv-sweep", "iv-breakdown", "iv-leakage"):
        _analyze_iv(filepath, flags)
    elif tech == "raman":
        _analyze_raman(filepath, flags)
    elif tech in ("uv-vis", "uv-vis-transmission", "uv-vis-absorbance"):
        _analyze_uv_vis(filepath, flags)
    else:
        console.print(f"[yellow]Unknown technique: {tech}. Trying CV analysis as default.[/yellow]")
        _analyze_cv(filepath, flags)

    # Sweep metadata: detect and store in protocol YAML
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session
    from science_cli.core.sweep_metadata import extract_sweep_from_file, update_protocol_with_sweep
    sess = load_session()
    pname = sess.get("last_protocol", "")
    proj = get_current_project_path()
    if pname and proj:
        paths = ProjectPaths(proj)
        yaml_path = paths.protocol_yaml(pname)
        if yaml_path.exists():
            fname = Path(filepath).name
            with open(yaml_path) as f:
                proto = yaml.safe_load(f) or {}

            for s in proto.get("steps", []):
                step_files = s.get("files", [])
                norm = [e["file"] if isinstance(e, dict) else e for e in step_files]
                if fname in norm:
                    segs = extract_sweep_from_file(filepath)
                    if segs:
                        update_protocol_with_sweep(yaml_path, s["name"], fname, segs)
                        ndirs = ", ".join(sg["direction"] for sg in segs)
                        console.print(f"  [dim]sweep: {len(segs)} seg [{ndirs}] @ {segs[0]['sweep_rate_v_s']} V/s[/dim]")
                    break


def _analyze_cv(filepath: str, flags: dict) -> None:
    import numpy as np

    from science_cli.core.data_loader import load_data_file
    from science_cli.library.electrochem.cv import calculate_charge, peak_analysis
    from science_cli.library.electrochem.models import CVData

    tech = _detect_technique(Path(filepath).name)
    device = _resolve_device(tech, filepath)
    if device:
        df, info = load_data_file(filepath, technique=tech, device=device)
    else:
        df, info = load_data_file(filepath)
    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Need at least 2 columns.[/red]")
        return

    p, c = df[cols[0]].values, df[cols[1]].values
    m = ~(np.isnan(p) | np.isnan(c))
    cv_data = CVData(potential=p[m], current=c[m], scan_rate=0.0)

    peaks = peak_analysis(cv_data)
    console.print(f"\n[bold]CV Analysis: {Path(filepath).name}[/bold]")
    console.print(f"  Anodic peaks: {peaks.get('n_anodic', 0)}")
    for pk in peaks.get("anodic_peaks", []):
        console.print(f"    E_pa={pk.get('potential',0):.4f}V  I_pa={pk.get('current',0):.4e}A")
    console.print(f"  Cathodic peaks: {peaks.get('n_cathodic', 0)}")
    for pk in peaks.get("cathodic_peaks", []):
        console.print(f"    E_pc={pk.get('potential',0):.4f}V  I_pc={pk.get('current',0):.4e}A")
    if "average_peak_separation" in peaks:
        console.print(f"  ΔE_p = {peaks['average_peak_separation']:.4f}V")

    if flags.get("charge"):
        charge = calculate_charge(cv_data)
        console.print(f"  Charge: {charge.get('total_charge',0):.4e}C")
        console.print(f"  Anodic: {charge.get('anodic_charge',0):.4e}C  Cathodic: {charge.get('cathodic_charge',0):.4e}C")

    _save_analysis_manifest(filepath, "CV", {"peaks": len(peaks.get("anodic_peaks", [])), "charge": flags.get("charge", False)})


def _analyze_ca(filepath: str, flags: dict) -> None:
    import numpy as np

    from science_cli.core.data_loader import load_data_file

    tech = _detect_technique(Path(filepath).name)
    device = _resolve_device(tech, filepath)
    if device:
        df, info = load_data_file(filepath, technique=tech, device=device)
    else:
        df, info = load_data_file(filepath)
    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Need at least 2 columns.[/red]")
        return
    t, i = df[cols[0]].values, df[cols[1]].values
    m = ~(np.isnan(t) | np.isnan(i))

    console.print(f"\n[bold]CA Analysis: {Path(filepath).name}[/bold]")

    from science_cli.library.electrochem.ca import analyze_ca as _analyze_ca_func
    from science_cli.library.electrochem.models import CAData
    ca_data = CAData(time=t[m], current=i[m])
    ca_result = _analyze_ca_func(ca_data, {"fit": flags.get("fit", True), "steady_state": True})
    if "cottrell" in ca_result:
        cr = ca_result["cottrell"]
        if "error" not in cr:
            console.print(f"  Cottrell slope: {cr.get('slope',0):.4e} A·√s  R²={cr.get('r_squared',0):.4f}")
        else:
            console.print(f"  [red]Cottrell fit failed: {cr['error']}[/red]")
    if "steady_state" in ca_result:
        ss = ca_result["steady_state"]
        console.print(f"  Steady state: {ss.get('steady_state_current',0):.4e}A")

    _save_analysis_manifest(filepath, "CA", {"fit": flags.get("fit", False)})


def _analyze_eis(filepath: str, flags: dict) -> None:
    import numpy as np

    from science_cli.core.data_loader import load_data_file

    def _col(candidates, cols):
        for c in candidates:
            if c in cols:
                return c
        return ""

    try:
        device = _resolve_device("ec-eis", filepath)
        if device:
            df, info = load_data_file(filepath, technique="ec-eis", device=device)
        else:
            df, info = load_data_file(filepath, technique="ec-eis")
    except Exception:
        df, info = load_data_file(filepath)
    cols = list(df.columns)
    freq_col = _col(["frequency", "Frequency (Hz)"], cols)
    zr_col = _col(["z_real", "Z' (Ω)", "Z'"], cols)
    zi_col = _col(["z_imag", "-Z'' (Ω)", "-Z''"], cols)
    if not freq_col or not zr_col or not zi_col:
        console.print("[red]Could not resolve EIS columns.[/red]")
        return
    freq = df[freq_col].values
    z = df[zr_col].values - 1j * df[zi_col].values
    m = ~(np.isnan(freq) | np.isnan(z.real) | np.isnan(z.imag))

    from science_cli.library.electrochem.eis import circuit_fit, kramers_kronig
    from science_cli.library.electrochem.models import EISData

    eis_data = EISData(frequency=freq[m], impedance=z[m])

    console.print(f"\n[bold]EIS Analysis: {Path(filepath).name}[/bold]")

    if flags.get("kk"):
        kk = kramers_kronig(eis_data)
        status = "✓ passed" if kk.get("passes") else "✗ failed"
        console.print(f"  KK test: {status}  (score={kk.get('consistency_score',0):.3f})")

    circuit = flags.get("circuit", "RRC")
    fit = circuit_fit(eis_data, circuit)
    console.print(f"  Circuit fit: {circuit}")
    if "error" in fit:
        console.print(f"  [red]Fit failed: {fit['error']}[/red]")
    else:
        for n, v in zip(fit.get("parameter_names", []), fit.get("fitted_params", [])):
            console.print(f"    {n}: {v:.4e}")
        console.print(f"    R²: {fit.get('r_squared',0):.4f}")

    _save_analysis_manifest(filepath, "EIS", {"circuit": circuit, "kk": flags.get("kk", False)})


def _get_step_dir(filepath: str) -> Path:
    """Derive the step directory from a file path."""
    from science_cli.core.paths import ProjectPaths
    from science_cli.core.project import get_current_project_path
    from science_cli.core.session import load_session
    session = load_session()
    current_protocol = session.get("last_protocol")
    proj = get_current_project_path()
    if current_protocol and proj:
        paths = ProjectPaths(proj)
        yaml_path = paths.protocol_yaml(current_protocol)
        if yaml_path.exists():
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            fname = Path(filepath).name
            for s in data.get("steps", []):
                step_files = s.get("files", [])
                norm = [e["file"] if isinstance(e, dict) else e for e in step_files]
                if fname in norm:
                    return paths.step_dir(current_protocol, s["name"])
    return Path(filepath).parent


def _output_yaml(technique: str, filepath: str, analysis_results: dict, flags: dict) -> None:
    """Handle --yaml flag: write YAML to results/ and optionally print to stdout."""
    from science_cli.core.analysis_output import write_analysis_yaml

    step_dir = _get_step_dir(filepath)
    yaml_path = write_analysis_yaml(
        technique=technique,
        step_dir=step_dir,
        analysis_results=analysis_results,
    )
    console.print(f"  [dim]YAML → {yaml_path}[/dim]")

    if flags.get("yaml"):
        import sys
        yaml.dump(analysis_results, sys.stdout, default_flow_style=False, sort_keys=False)


def _analyze_iv(filepath: str, flags: dict) -> None:
    """Analyze IV sweep file."""
    import numpy as np

    from science_cli.core.data_loader import load_data_file
    from science_cli.library.iv.metrics import detect_vset, detect_vreset, extract_iv_parameters

    tech = _detect_technique(Path(filepath).name)

    device = _resolve_device(tech, filepath)
    if device:
        df, info = load_data_file(filepath, technique=tech, device=device)
    else:
        df, info = load_data_file(filepath)
    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Need at least 2 columns for IV analysis.[/red]")
        return

    v = df[cols[0]].values
    i = df[cols[1]].values
    mask = ~(np.isnan(v) | np.isnan(i))

    params = extract_iv_parameters(v[mask], i[mask])

    console.print(f"\n[bold]IV Analysis: {Path(filepath).name}[/bold]")
    console.print(f"  V_set = {params.get('v_set', 'N/A')}")
    console.print(f"  V_reset = {params.get('v_reset', 'N/A')}")
    console.print(f"  ON/OFF ratio = {params.get('on_off_ratio', 'N/A')}")

    # Determine mode from flags or device type
    mode = "volatile" if flags.get("vset_only") else "general"

    analysis_results = {
        "analysis": {
            "mode": mode,
            "parameters": {
                "v_set": params.get("v_set"),
                "v_reset": params.get("v_reset"),
                "on_off_ratio": params.get("on_off_ratio"),
                "switching_detected": params.get("switching_detected", False),
            },
        },
    }

    if flags.get("yaml"):
        _output_yaml(tech or "iv-sweep", filepath, analysis_results, flags)


def _analyze_raman(filepath: str, flags: dict) -> None:
    """Analyze Raman spectrum file."""
    import numpy as np

    from science_cli.core.data_loader import load_data_file

    df, info = load_data_file(filepath, technique="raman")
    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Need at least 2 columns for Raman analysis.[/red]")
        return

    x = df[cols[0]].values
    y = df[cols[1]].values
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    # Simple peak detection
    from scipy import signal
    peaks, props = signal.find_peaks(y, prominence=0.1 * np.max(y))
    peak_list = []
    for p in peaks:
        peak_list.append({
            "wavenumber_cm": float(x[p]),
            "intensity": float(y[p]),
        })

    console.print(f"\n[bold]Raman Analysis: {Path(filepath).name}[/bold]")
    console.print(f"  Peaks found: {len(peak_list)}")
    for pk in peak_list[:10]:
        console.print(f"    {pk['wavenumber_cm']:.1f} cm⁻¹  (I={pk['intensity']:.1f})")
    if len(peak_list) > 10:
        console.print(f"    ... and {len(peak_list) - 10} more")

    analysis_results = {
        "analysis": {
            "peaks": peak_list,
            "preprocessing": [],
        },
    }

    if flags.get("yaml"):
        _output_yaml("raman-spectrum", filepath, analysis_results, flags)


def _analyze_uv_vis(filepath: str, flags: dict) -> None:
    """Analyze UV-Vis spectrum file."""
    import numpy as np

    from science_cli.core.data_loader import load_data_file

    tech = _detect_technique(Path(filepath).name)
    df, info = load_data_file(filepath, technique="uv-vis")
    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Need at least 2 columns for UV-Vis analysis.[/red]")
        return

    x = df[cols[0]].values
    y = df[cols[1]].values
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    # Simple peak detection
    from scipy import signal
    peaks, props = signal.find_peaks(y, prominence=0.05 * np.max(y))
    peak_list = []
    for p in peaks:
        peak_list.append({
            "wavelength_nm": float(x[p]),
            "absorbance": float(y[p]),
        })

    console.print(f"\n[bold]UV-Vis Analysis: {Path(filepath).name}[/bold]")
    console.print(f"  Peaks found: {len(peak_list)}")
    for pk in peak_list[:10]:
        console.print(f"    {pk['wavelength_nm']:.1f} nm  (A={pk['absorbance']:.3f})")
    if len(peak_list) > 10:
        console.print(f"    ... and {len(peak_list) - 10} more")

    analysis_results = {
        "analysis": {
            "peaks": peak_list,
        },
    }

    if flags.get("yaml"):
        _output_yaml(tech or "uv-vis-transmission", filepath, analysis_results, flags)


def _analyze_pulse_endurance(
    filepath: str,
    flags: dict,
    device_type: str | None = None,
    study_name: str | None = None,
) -> None:
    """Analyze pulse endurance data, potentially device-type-specific.

    When ``device_type`` is "volatile-memristor":
        future: ON/OFF ratio, STP-like decay, read-disturb analysis.
    When ``device_type`` is "non-volatile-memristor":
        future: HRS/LRS separation, window margin, retention drift.

    Currently a stub — delegates to the generic message.
    """
    if device_type:
        console.print(
            f"[dim]Pulse endurance analysis ({device_type}) "
            f"not yet implemented. Use 'pulse analyze' instead.[/dim]"
        )
    else:
        console.print(
            "[yellow]Pulse endurance analysis not yet implemented. "
            "Use 'pulse analyze' instead.[/yellow]"
        )


def _analyze_pulse_retention(filepath: str, flags: dict) -> None:
    console.print("[yellow]Pulse retention analysis not yet implemented. Use 'pulse analyze' instead.[/yellow]")


def _analyze_pulse_stp(filepath: str, flags: dict) -> None:
    console.print("[yellow]STP decay analysis not yet implemented. Use 'pulse analyze' instead.[/yellow]")


def _analyze_pulse_ppf(filepath: str, flags: dict) -> None:
    console.print("[yellow]PPF analysis not yet implemented. Use 'pulse analyze' instead.[/yellow]")


def _analyze_afm(filepath: str, flags: dict) -> None:
    console.print("[yellow]AFM analysis not yet implemented. Use 'afm analyze' instead.[/yellow]")


def _validate_analyze_flags(flags: dict, technique: str = "") -> list[str]:
    warnings: list[str] = []
    if not technique:
        return warnings
    known_flags: set[str] = set()
    for entry in ANALYZE_TECHNIQUE_FLAGS.get(technique, []):
        known_flags.add(entry["name"])
    for flag in flags:
        if flag in ("technique", "t"):
            continue
        flag_name = f"--{flag}"
        if flag_name in known_flags:
            continue
        for other_tech, other_flags in ANALYZE_TECHNIQUE_FLAGS.items():
            if other_tech == technique:
                continue
            for entry in other_flags:
                if flag_name == entry["name"]:
                    warnings.append(f"'{flag_name}' is for technique '{other_tech}', not '{technique}'")
                    break
    return warnings


def _analyze_with_technique(
    technique: str,
    flags: dict,
    study_name: str = "",
    device_type: str | None = None,
) -> None:
    """Fzf-select a file, then analyze with explicit technique context.

    When ``device_type`` is provided, it is passed through to the
    analyzer function for device-type-aware behavior (e.g. volatile
    vs non-volatile pulse endurance analysis).
    """
    from science_cli.core.project import get_current_project_path
    from science_cli.core.fzf_utils import fzf_select

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

    item_names = [f.name for f in files]
    selected = fzf_select(item_names, prompt=f"Select file for {technique} analysis:", multi=False)
    if not selected:
        return

    filepath = str(raw_dir / selected[0])

    analyzer_name = TECHNIQUE_ANALYZERS.get(technique)
    if analyzer_name:
        import importlib
        module = importlib.import_module("science_cli.cli.commands.analyze")
        analyzer = getattr(module, analyzer_name)
        # Pass device_type and study_name as keyword args for analyzers
        # that use them (stubs accept **kwargs or have explicit params)
        _call_analyzer_with_context(analyzer, filepath, flags, study_name, device_type)
    else:
        console.print(f"[yellow]No analyzer registered for technique '{technique}'. Falling back to auto-detect.[/yellow]")
        _analyze_direct([filepath], [])


def _call_analyzer_with_context(
    analyzer,
    filepath: str,
    flags: dict,
    study_name: str | None = None,
    device_type: str | None = None,
) -> None:
    """Invoke analyzer with device-type and study context when supported.

    Tries the analyzer with keyword args first (device_type, study_name),
    falling back to positional-only call for analyzers that don't accept them.
    """
    import inspect
    sig = inspect.signature(analyzer)
    params = sig.parameters
    kwargs: dict[str, str | None] = {}
    if "device_type" in params and device_type:
        kwargs["device_type"] = device_type
    if "study_name" in params and study_name:
        kwargs["study_name"] = study_name
    try:
        if kwargs:
            analyzer(filepath, flags, **kwargs)
        else:
            analyzer(filepath, flags)
    except TypeError:
        # Fallback to positional-only for stubs that don't accept kwargs
        analyzer(filepath, flags)


def _save_analysis_manifest(filepath: str, technique: str, results: dict) -> None:
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

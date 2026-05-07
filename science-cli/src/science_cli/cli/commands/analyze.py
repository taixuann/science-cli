"""analyze command handler — analysis only (no plotting)."""

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

    if tech == "cv":
        _analyze_cv(filepath, flags)
    elif tech == "ca":
        _analyze_ca(filepath, flags)
    elif tech == "eis":
        _analyze_eis(filepath, flags)
    else:
        console.print(f"[yellow]Unknown technique: {tech}. Trying CV analysis as default.[/yellow]")
        _analyze_cv(filepath, flags)

    # Sweep metadata: detect and store in protocol YAML
    from science_cli.core.sweep_metadata import extract_sweep_from_file, update_protocol_with_sweep
    from science_cli.core.session import load_session
    from science_cli.core.project import get_current_project_path
    from science_cli.core.paths import ProjectPaths
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
    from science_cli.core.data_loader import load_data_file
    import numpy as np
    from science_electrochem.cv import peak_analysis, calculate_charge
    from science_electrochem.models import CVData

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
    from science_cli.core.data_loader import load_data_file
    import numpy as np

    df, info = load_data_file(filepath)
    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Need at least 2 columns.[/red]")
        return
    t, i = df[cols[0]].values, df[cols[1]].values
    m = ~(np.isnan(t) | np.isnan(i))

    console.print(f"\n[bold]CA Analysis: {Path(filepath).name}[/bold]")

    from science_electrochem.models import CAData
    from science_electrochem.ca import analyze_ca as _analyze_ca_func
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
    from science_cli.core.data_loader import load_data_file
    import numpy as np

    df, info = load_data_file(filepath)
    cols = info.get("columns", [])
    if len(cols) < 3:
        console.print("[red]Need freq, Z', Z'' columns.[/red]")
        return
    freq = df[cols[0]].values
    z = df[cols[1]].values + 1j * df[cols[2]].values
    m = ~(np.isnan(freq) | np.isnan(z.real) | np.isnan(z.imag))

    from science_electrochem.eis import circuit_fit, kramers_kronig
    from science_electrochem.models import EISData

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
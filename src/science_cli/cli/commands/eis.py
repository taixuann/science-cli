"""eis command handler — kk, fit, batch, simulate, export."""

from pathlib import Path

from rich.console import Console

from science_cli.cli.help import show_command_help
from science_cli.core.data_loader import load_data_file
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


def _get_eis_data(filepath: str):
    import numpy as np

    from science_cli.library.electrochem.models import EISData

    def _col(candidates, cols):
        for c in candidates:
            if c in cols:
                return c
        return ""

    try:
        df, info = load_data_file(filepath, technique="ec-eis")
    except Exception:
        df, info = load_data_file(filepath)
    cols = list(df.columns)
    freq_col = _col(["frequency", "Frequency (Hz)"], cols)
    zr_col = _col(["z_real", "Z' (Ω)", "Z'"], cols)
    zi_col = _col(["z_imag", "-Z'' (Ω)", "-Z''"], cols)
    if not freq_col or not zr_col or not zi_col:
        console.print("[red]Could not resolve EIS columns.[/red]")
        return None
    freq = df[freq_col].values
    z = df[zr_col].values - 1j * df[zi_col].values
    m = ~(np.isnan(freq) | np.isnan(z.real) | np.isnan(z.imag))
    return EISData(frequency=freq[m], impedance=z[m])


def eis_handler(args: list) -> None:
    """Handle `eis` command and subcommands."""
    if not args or args[0] in ("--help", "-h"):
        show_command_help("eis")
        return

    sub = args[0]
    sub_args = args[1:]

    sub_map = {
        "kk": _eis_kk,
        "fit": _eis_fit,
        "batch": _eis_batch,
        "simulate": _eis_simulate,
        "export": _eis_export,
    }

    handler = sub_map.get(sub)
    if handler:
        handler(sub_args)
    else:
        console.print(f"[yellow]Unknown eis subcommand: {sub}[/yellow]")
        show_command_help("eis")


def _eis_kk(args: list) -> None:
    positional, _ = _parse_flags(args)
    if not positional:
        console.print("[yellow]Usage: eis kk <file>[/yellow]")
        return
    filepath = _resolve_file(positional[0])
    if not filepath:
        console.print(f"[red]File not found: {positional[0]}[/red]")
        return
    from science_cli.library.electrochem.eis import kramers_kronig
    data = _get_eis_data(filepath)
    if data is None:
        return
    kk = kramers_kronig(data)
    status = "✓ passed" if kk.get("passes") else "✗ failed"
    console.print(f"\n[bold]KK Test: {Path(filepath).name}[/bold]")
    console.print(f"  Status: {status}")
    console.print(f"  Score:  {kk.get('consistency_score',0):.4f}")
    console.print(f"  Points: {kk.get('n_points',0)}")


def _eis_fit(args: list) -> None:
    positional, flags = _parse_flags(args)
    if not positional:
        console.print("[yellow]Usage: eis fit <file> [--circuit MODEL][/yellow]")
        return
    filepath = _resolve_file(positional[0])
    if not filepath:
        console.print(f"[red]File not found: {positional[0]}[/red]")
        return
    from science_cli.library.electrochem.eis import circuit_fit
    data = _get_eis_data(filepath)
    if data is None:
        return
    circuit = flags.get("circuit", "RRC")
    fit = circuit_fit(data, circuit)
    console.print(f"\n[bold]Circuit Fit: {Path(filepath).name}  [{circuit}][/bold]")
    if "error" in fit:
        console.print(f"  [red]{fit['error']}[/red]")
    else:
        for n, v in zip(fit.get("parameter_names", []), fit.get("fitted_params", [])):
            console.print(f"  {n}: {v:.4e}")
        console.print(f"  R²: {fit.get('r_squared',0):.4f}")


def _eis_batch(args: list) -> None:
    from science_cli.core.project import get_current_project_path
    from science_cli.library.electrochem.eis import circuit_fit
    proj = get_current_project_path()
    if not proj:
        console.print("[yellow]No project open.[/yellow]")
        return
    raw_dir = proj / "data" / "raw"
    if not raw_dir.exists():
        console.print("[yellow]No data/raw directory.[/yellow]")
        return
    files = sorted([f for f in raw_dir.iterdir() if f.is_file() and not f.name.startswith(".") and "eis" in f.name.lower()])
    if not files:
        console.print("[yellow]No EIS files found.[/yellow]")
        return
    circuit = "RRC"
    console.print(f"\n[bold]Batch EIS Fit ({circuit})[/bold]")
    for f in files:
        try:
            data = _get_eis_data(str(f))
            if data is None:
                continue
            fit = circuit_fit(data, circuit)
            r2 = fit.get("r_squared", 0)
            console.print(f"  {f.name}: R²={r2:.4f}")
        except Exception as e:
            console.print(f"  {f.name}: [red]FAILED ({e})[/red]")


def _eis_simulate(args: list) -> None:
    console.print("[yellow]EIS simulation not yet implemented.[/yellow]")
    console.print("[dim]Use the PyEIS library for full simulation support.[/dim]")


def _eis_export(args: list) -> None:
    positional, flags = _parse_flags(args)
    if not positional:
        console.print("[yellow]Usage: eis export <file>[/yellow]")
        return
    filepath = _resolve_file(positional[0])
    if not filepath:
        console.print(f"[red]File not found: {positional[0]}[/red]")
        return
    from science_cli.library.electrochem.eis import circuit_fit
    data = _get_eis_data(filepath)
    if data is None:
        return
    circuit = flags.get("circuit", "RRC")
    fit = circuit_fit(data, circuit)
    if "error" in fit:
        console.print(f"[red]{fit['error']}[/red]")
        return
    import json
    result = {
        "file": filepath,
        "circuit": circuit,
        "parameters": dict(zip(fit.get("parameter_names", []), [float(v) for v in fit.get("fitted_params", [])])),
        "r_squared": float(fit.get("r_squared", 0)),
    }
    from science_cli.core.project import get_current_project_path
    proj = get_current_project_path()
    if proj:
        out_dir = proj / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{Path(filepath).stem}_eis_fit.json"
        with open(out_file, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"  [green]✓[/green] Exported to {out_file}")
    else:
        console.print(json.dumps(result, indent=2))

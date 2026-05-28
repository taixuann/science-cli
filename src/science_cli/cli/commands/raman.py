"""raman command handler — list, inspect, plot, and analyze Raman spectra."""

from pathlib import Path

import numpy as np
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

    names = [f.name for f in files]
    selected = fzf_select(
        items=names,
        prompt=prompt,
        multi=False,
        preview=f"head -n 20 {raw_dir}/{{}}",
        preview_window="right:50%:border-sharp",
    )
    if not selected:
        return None

    return str(raw_dir / selected[0])


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
        if not sub_args or sub_args[0].startswith("--"):
            _raman_info("--fzf")
        else:
            _raman_info(sub_args[0])
    elif sub == "plot":
        if not sub_args or sub_args[0].startswith("--"):
            _raman_plot("--fzf", sub_args)
        else:
            _raman_plot(sub_args[0], sub_args[1:])
    elif sub == "analyze":
        pos, flags = _parse_flags(sub_args)
        if not pos:
            picked = _raman_fzf_pick_single("Select Raman file for analysis")
            if not picked:
                return
            _raman_analyze(picked, flags)
        _raman_analyze(pos[0], flags)
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
                raman_files = [f for f in files if f.is_file() and f.name != "results"]
            else:
                console.print(f"[yellow]Step '{step_name}' not found.[/yellow]")
                return
        else:
            console.print("[yellow]No project open.[/yellow]")
            return
    else:
        raman_files = _get_raman_files(raw_dir)

    if not raman_files:
        console.print("[yellow]No Raman files found.[/yellow]")
        return

    table = Table(title=f"Raman Files{' — ' + step_name if step_name else ''}", border_style="cyan")
    table.add_column("File", style="bold white")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Laser", style="yellow")
    table.add_column("Grating", style="green")
    table.add_column("Range", style="dim")

    for f in raman_files:
        size = f.stat().st_size
        meta = extract_raman_metadata(str(f))
        laser = meta.get("laser", "")
        grating = meta.get("grating", "")
        rng = meta.get("range", "")
        table.add_row(
            f.name,
            f"{size / 1024:.1f}KB" if size >= 1024 else f"{size}B",
            laser,
            grating,
            rng,
        )

    console.print(table)


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


def _raman_info(filename_or_fzf: str) -> None:
    if filename_or_fzf == "--fzf":
        picked = _raman_fzf_pick_single("Select Raman file for info")
        if not picked:
            return
        filename_or_fzf = picked

    filepath = _resolve_file(filename_or_fzf)
    if not filepath:
        console.print(f"[red]File not found: {filename_or_fzf}[/red]")
        return

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


def _raman_plot(filename_or_fzf: str, plot_args: list) -> None:
    import matplotlib.pyplot as plt

    if filename_or_fzf == "--fzf":
        picked = _raman_fzf_pick_single("Select Raman file for plot")
        if not picked:
            return
        filename_or_fzf = picked

    pos, flags = _parse_flags(plot_args)
    filepath = _resolve_file(filename_or_fzf)
    if not filepath:
        console.print(f"[red]File not found: {filename_or_fzf}[/red]")
        return

    p = Path(filepath)

    try:
        df, info = load_data_file(str(p), technique="raman", device="horiba-usth")
    except Exception:
        df, info = load_data_file(str(p))

    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Not enough columns in data.[/red]")
        return

    shift = df[cols[0]].values
    intensity = df[cols[1]].values
    mask = ~(np.isnan(shift) | np.isnan(intensity) | (shift <= 0))

    if not mask.any():
        console.print("[red]No valid data points.[/red]")
        return

    shift = shift[mask]
    intensity = intensity[mask]

    meta = info.get("raman_metadata", {})
    title = flags.get("title") or p.stem
    xlabel = flags.get("xlabel") or "Raman shift (cm⁻¹)"
    ylabel = flags.get("ylabel") or "Intensity (counts)"

    plt.figure(figsize=(10, 5))
    plt.plot(shift, intensity, color="#1f77b4", linewidth=1.2)

    laser = meta.get("laser", "")
    grating = meta.get("grating", "")
    subtitle = f"  [{laser} | {grating}]" if laser and grating else ""

    plt.title(f"{title}{subtitle}", fontsize=12)
    plt.xlabel(xlabel, fontsize=11)
    plt.ylabel(ylabel, fontsize=11)

    if flags.get("grid"):
        plt.grid(True, alpha=0.3)

    xlim = flags.get("xlim")
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

    out_name = flags.get("name", "")
    if out_name:
        save_path = Path(out_name)
        if not save_path.suffix:
            save_path = save_path.with_suffix(".pdf")
        plt.savefig(save_path, dpi=int(flags.get("dpi", 300)))
        console.print(f"[green]✓[/green] Saved to {save_path}")
    else:
        plt.show()

    plt.close()


# ── Analyze ──────────────────────────────────────────────────────────


def _asls_baseline(y: np.ndarray, lam: float = 1e7, p: float = 0.01, niter: int = 10) -> np.ndarray:
    """Asymmetric Least Squares (ASLS) baseline correction.

    Parameters
    ----------
    y : ndarray
        Input signal.
    lam : float
        Smoothness parameter (larger = smoother baseline).
    p : float
        Asymmetry parameter (closer to 0 = more asymmetric).
    niter : int
        Max iterations.

    Returns
    -------
    ndarray
        Fitted baseline of same length as y.
    """
    from scipy import sparse
    from scipy.sparse.linalg import spsolve

    n = len(y)
    d2 = sparse.diags([1, -2, 1], [0, 1, 2], shape=(n - 2, n), format="csc", dtype=float)
    w = np.ones(n)
    for _ in range(niter):
        w_diag = sparse.diags(w, 0, shape=(n, n), format="csc")
        mat = (w_diag + lam * (d2.T @ d2)).tocsc()
        z = spsolve(mat, w * y)
        w_new = p * (y > z) + (1 - p) * (y < z)
        if np.sum(np.abs(w_new - w)) < 1e-6 * n:
            break
        w = w_new
    return z


def _raman_analyze(filepath: str, flags: dict) -> None:
    from scipy.signal import find_peaks, peak_widths

    resolved = _resolve_file(filepath)
    if not resolved:
        console.print(f"[red]File not found: {filepath}[/red]")
        return

    p = Path(resolved)

    try:
        df, info = load_data_file(str(p), technique="raman", device="horiba-usth")
    except Exception:
        df, info = load_data_file(str(p))

    cols = info.get("columns", [])
    if len(cols) < 2:
        console.print("[red]Not enough columns in data.[/red]")
        return

    shift = df[cols[0]].values.astype(float)
    intensity = df[cols[1]].values.astype(float)
    mask = ~(np.isnan(shift) | np.isnan(intensity) | (shift <= 0))

    if not mask.any():
        console.print("[red]No valid data points.[/red]")
        return

    shift = shift[mask]
    intensity = intensity[mask]

    console.print(f"\n[bold]Raman Analysis: {p.name}[/bold]")
    console.print(f"  Data points: {len(shift)}")

    # 1. Baseline correction (ASLS)
    if flags.get("baseline"):
        lam = float(flags.get("lam", 1e7))
        asym_p = float(flags.get("p", 0.01))
        console.print(f"  Baseline correction: ASLS (lam={lam:.0e}, p={asym_p})")
        baseline = _asls_baseline(intensity, lam=lam, p=asym_p)
        intensity_corrected = intensity - baseline
        baseline_subtracted = True
    else:
        baseline = None
        intensity_corrected = intensity
        baseline_subtracted = False

    # 2. Normalization (max-intensity)
    if flags.get("norm"):
        max_int = np.max(intensity_corrected)
        if max_int > 0:
            intensity_final = intensity_corrected / max_int
            norm_factor = max_int
            normalized = True
        else:
            intensity_final = intensity_corrected
            norm_factor = 1.0
            normalized = False
        console.print(f"  Max-intensity normalization: factor={norm_factor:.2f}" if normalized else "  [yellow]Normalization skipped (max=0)[/yellow]")
    else:
        intensity_final = intensity_corrected
        normalized = False

    # 3. Peak finding — default prominence: 15% of max intensity
    max_int = float(np.max(intensity_final)) if len(intensity_final) > 0 else 1.0
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

    peaks, props = find_peaks(intensity_final, **peak_kwargs)

    if len(peaks) == 0:
        console.print(f"  [yellow]No peaks found with prominence={prominence}. Try --prominence <lower>[/yellow]")
    else:
        # Calculate widths (FWHM in cm⁻¹)
        try:
            widths_result = peak_widths(intensity_final, peaks, rel_height=0.5)
            left_ips = widths_result[2]
            right_ips = widths_result[3]
            fwhms = shift[np.minimum(np.round(right_ips).astype(int), len(shift) - 1)] - shift[np.minimum(np.round(left_ips).astype(int), len(shift) - 1)]
        except Exception:
            fwhms = np.full(len(peaks), np.nan)

        peak_shifts = shift[peaks]
        peak_intensities = intensity_final[peaks]
        peak_prominences = props.get("prominences", np.full(len(peaks), np.nan))

        # Peaks table
        peak_table = Table(title=f"Detected Peaks ({len(peaks)} found)", border_style="green")
        peak_table.add_column("#", style="dim", justify="right")
        peak_table.add_column("Shift (cm⁻¹)", style="bold cyan", justify="right")
        if normalized:
            peak_table.add_column("Intensity (a.u.)", justify="right")
        else:
            peak_table.add_column("Intensity (counts)", justify="right")
        peak_table.add_column("Prominence", justify="right")
        peak_table.add_column("FWHM (cm⁻¹)", justify="right")

        for i, (s, v, prom, fw) in enumerate(zip(peak_shifts, peak_intensities, peak_prominences, fwhms)):
            fw_str = f"{fw:.1f}" if not np.isnan(fw) else "—"
            peak_table.add_row(
                str(i + 1),
                f"{s:.1f}",
                f"{v:.4e}" if not normalized else f"{v:.4f}",
                f"{prom:.1f}",
                fw_str,
            )

        console.print(peak_table)

    # 4. Save CSV outputs
    out_dir = _get_results_dir(resolved)
    prefix = flags.get("name") or p.stem

    saved = []

    if len(peaks) > 0:
        import pandas as pd
        peaks_df = pd.DataFrame({
            "peak_center(cm⁻¹)": peak_shifts,
            "intensity(counts)" if not normalized else "intensity(a.u.)": peak_intensities,
            "prominence": peak_prominences,
            "fwhm(cm⁻¹)": fwhms,
        })
        peaks_csv = out_dir / f"{prefix}_peaks.csv"
        peaks_df.to_csv(peaks_csv, index=False)
        saved.append(peaks_csv)

    if baseline_subtracted and baseline is not None:
        import pandas as pd
        baseline_df = pd.DataFrame({
            "shift(cm⁻¹)": shift,
            "baseline(counts)": baseline,
        })
        baseline_csv = out_dir / f"{prefix}_baseline.csv"
        baseline_df.to_csv(baseline_csv, index=False)
        saved.append(baseline_csv)

    if normalized:
        import pandas as pd
        norm_df = pd.DataFrame({
            "shift(cm⁻¹)": shift,
            "intensity(a.u.)": intensity_final,
        })
        norm_csv = out_dir / f"{prefix}_normalized.csv"
        norm_df.to_csv(norm_csv, index=False)
        saved.append(norm_csv)

    if saved:
        console.print("\n[bold green]Saved:[/bold green]")
        for csv_path in saved:
            console.print(f"  ✓ {csv_path}")
    else:
        console.print("\n[yellow]No output files saved. Use --baseline and/or --norm to generate CSV output.[/yellow]")

    # Console summary
    if len(peaks) > 0:
        console.print(f"\n  [bold]Summary:[/bold] {len(peaks)} peaks detected")
        major = [s for s in peak_shifts if s > 500]
        if major:
            console.print(f"  Major bands: {', '.join(f'{s:.0f} cm⁻¹' for s in major[:5])}")
            if len(major) > 5:
                console.print(f"    ... and {len(major) - 5} more")

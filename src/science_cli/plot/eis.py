"""EIS-specific plotting: Nyquist, Bode."""

from pathlib import Path

import numpy as np

from science_cli.plot.base import (
    apply_figure_kw,
    create_figure,
    parse_figsize,
    plot_line,
)


def _ensure_neg_imag(z_imag):
    """Ensure z_imag represents -Z'' (positive upward).

    Normalized column z_imag stores the raw column value. If the raw column
    was named "-Z'' (Ω)" (Autolab convention), values are already positive.
    If named "Z'' (Ω)" (other instruments), values are negative for capacitive.
    Detect by sign of min value and negate if needed so -Z'' sits on +y axis.
    """
    return -z_imag if np.min(z_imag) < 0 else z_imag


def plot_eis_nyquist(
    z_real: np.ndarray,
    z_imag: np.ndarray,
    flags: dict | None = None,
    label: str = "",
    ax=None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    if ax is None:
        fig, ax = create_figure(flags.get("theme", "publication-nature"), figsize)
    else:
        fig = ax.figure

    y = _ensure_neg_imag(z_imag)
    plot_line(z_real, y, ax=ax, flags=flags, label=label)

    apply_figure_kw(ax, flags)
    if not flags.get("xlabel"):
        ax.set_xlabel("Z' (Ω)")
    if not flags.get("ylabel"):
        ax.set_ylabel("-Z'' (Ω)")
    ax.set_aspect("equal")

    return fig, ax


def plot_eis_bode(
    frequency: np.ndarray,
    magnitude: np.ndarray,
    phase: np.ndarray | None = None,
    flags: dict | None = None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)

    fig, ax1 = create_figure(flags.get("theme", ""), figsize=figsize)

    mag_flags = dict(flags)
    from science_cli.core.plot_config import resolve_plot_config
    _eis_cfg = resolve_plot_config("ec:ec-eis")
    mag_flags.setdefault("color", _eis_cfg.get("series.bode.color", "#2563eb"))
    plot_line(frequency, magnitude, ax=ax1, flags=mag_flags)
    ax1.set_ylabel("|Z| (Ω)")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.grid(True, alpha=0.3)

    if phase is not None:
        ax2 = ax1.twinx()
        phase_flags = dict(flags)
        phase_flags["color"] = _eis_cfg.get("series.phase.color", "#dc2626")
        plot_line(frequency, phase, ax=ax2, flags=phase_flags)
        ax2.set_ylabel("Phase (°)")
        ax2.set_xscale("log")
        ax2.set_xlabel("Frequency (Hz)")
        ax2.grid(True, alpha=0.3)

    return fig, ax1


def plot_eis_fit(
    z_real: np.ndarray,
    z_imag: np.ndarray,
    fit_real: np.ndarray,
    fit_imag: np.ndarray,
    flags: dict | None = None,
):
    flags = flags or {}
    figsize = parse_figsize(flags)
    fig, ax = create_figure(flags.get("theme", "default"), figsize)

    y_data = _ensure_neg_imag(z_imag)
    y_fit = _ensure_neg_imag(fit_imag)
    plot_line(z_real, y_data, ax=ax, flags=flags, label="Data")
    from science_cli.core.plot_config import resolve_plot_config
    _eis_cfg = resolve_plot_config("ec:ec-eis")
    fit_flags = dict(flags)
    fit_flags["linestyle"] = "--"
    fit_flags["color"] = _eis_cfg.get("series.fit.color", "red")
    fit_flags.pop("marker", None)
    plot_line(fit_real, y_fit, ax=ax, flags=fit_flags, label="Fit")

    ax.set_xlabel("Z' (Ω)")
    ax.set_ylabel("-Z'' (Ω)")
    ax.set_aspect("equal")
    ax.legend()
    apply_figure_kw(ax, flags)

    return fig, ax


def _plot_eis_single(filepath: str, flags: dict) -> None:
    """EIS single: Nyquist + Bode, with --circuit fit option."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir
    from science_cli.core.device_resolver import resolve_device as _resolve_device
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.library.electrochem.models import EISData
    from science_cli.plot.base import apply_figure_kw
    from science_cli.plot.eis import plot_eis_bode, plot_eis_fit, plot_eis_nyquist
    from science_cli.theme import apply_theme

    console = Console()
    try:
        load_kwargs = {"technique": "ec-eis"}
        device = _resolve_device("ec-eis", filepath)
        if device:
            load_kwargs["device"] = device
        df, info = load_data_file(filepath, **load_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to load EIS data: {e}[/red]")
        return

    cols = list(df.columns)
    def _col(candidates):
        for c in candidates:
            if c in cols:
                return c
        return ""
    freq_col = _col(["frequency", "Frequency (Hz)"])
    z_real_col = _col(["z_real", "Z' (Ω)", "Z'"])
    z_imag_col = _col(["z_imag", "-Z'' (Ω)", "-Z''"])
    mag_col = _col(["magnitude", "Z (Ω)"])
    phase_col = _col(["phase", "-Phase (°)", "Phase (°)"])

    if not freq_col or not z_real_col or not z_imag_col:
        console.print("[red]EIS data missing columns.[/red]")
        return

    freq = df[freq_col].values
    z_real = df[z_real_col].values
    z_imag = df[z_imag_col].values
    mag = df[mag_col].values if mag_col else None
    phase = df[phase_col].values if phase_col else None

    apply_theme(get_active_theme())
    stem = Path(filepath).stem
    out_dir = _get_results_dir(filepath)
    _def_dpi = int(mpl.rcParams.get("savefig.dpi", 600))
    dpi = int(flags.get("dpi", _def_dpi))
    want_nyquist = not flags.get("bode")
    want_bode = not flags.get("nyquist")
    output_files = []

    if want_nyquist:
        fig, ax = plot_eis_nyquist(z_real, z_imag, label=stem)
        apply_figure_kw(ax, flags, stem)
        nyq_name = f"ec-eis-nyquist_{stem}.pdf"
        nyq_path = out_dir / nyq_name
        fig.savefig(nyq_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        console.print(f"[bold green]✓[/bold green] Nyquist saved: {nyq_path}")
        output_files.append(str(nyq_path))

    if want_bode and freq_col and mag_col and phase_col:
        fig, ax1 = plot_eis_bode(freq, mag, phase)
        apply_figure_kw(ax1, flags, stem)
        bode_name = f"ec-eis-bode_{stem}.pdf"
        bode_path = out_dir / bode_name
        fig.savefig(bode_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        console.print(f"[bold green]✓[/bold green] Bode saved: {bode_path}")
        output_files.append(str(bode_path))

    circuit_model = flags.get("circuit")
    if circuit_model is not False and circuit_model is not None:
        from science_cli.library.electrochem.eis import best_circuit_fit, circuit_fit
        eis_data = EISData(frequency=freq, impedance=z_real - 1j * z_imag)
        if isinstance(circuit_model, str) and circuit_model not in (True, ""):
            fit = circuit_fit(eis_data, circuit_model)
        else:
            fit = best_circuit_fit(eis_data, candidates=["R_s(C[RW])", "R_s(Q[RW])"])
            circuit_model = fit.get("circuit", "best")
        if "error" not in fit:
            fz = np.array(fit.get("fit_Z_real", []))
            fzi = np.array(fit.get("fit_Z_imag", []))
            if len(fz) > 0:
                fig, ax = plot_eis_fit(z_real, z_imag, fz, fzi)
                apply_figure_kw(ax, flags, stem)
                fit_name = f"ec-eis-fit-nyquist_{stem}.pdf"
                fit_path = out_dir / fit_name
                fig.savefig(fit_path, dpi=dpi, bbox_inches="tight")
                plt.close(fig)
                console.print(f"[bold green]✓[/bold green] Fit overlay saved: {fit_path}")
                output_files.append(str(fit_path))
            import json
            fit_json = {
                "file": Path(filepath).name,
                "circuit": circuit_model,
                "r_squared": fit.get("r_squared", 0),
                "reduced_chi": fit.get("reduced_chi", 0),
                "nfev": fit.get("nfev", 0),
                "parameters": {
                    n: {"value": v, "stderr": s}
                    for n, v, s in zip(fit.get("parameter_names", []),
                                       fit.get("fitted_params", []),
                                       fit.get("param_stderr", []))
                },
            }
            json_name = f"ec-eis-fit-nyquist_{stem}.json"
            json_path = out_dir / json_name
            with open(json_path, "w") as jf:
                json.dump(fit_json, jf, indent=2)
            console.print(f"[bold green]✓[/bold green] Fit results saved: {json_path}")
            output_files.append(str(json_path))
            console.print(f"\n  [bold]Circuit fit:[/bold] {circuit_model}  (R²={fit.get('r_squared', 0):.4f})")
            for n, v in zip(fit.get("parameter_names", []), fit.get("fitted_params", [])):
                console.print(f"    {n}: {v:.4e}")
        else:
            console.print(f"  [red]Fit failed: {fit['error']}[/red]")

    if flags.get("kk"):
        from science_cli.library.electrochem.eis import kramers_kronig
        eis_data = EISData(frequency=freq, impedance=z_real - 1j * z_imag)
        kk = kramers_kronig(eis_data)
        status = "✓ passed" if kk.get("passes") else "✗ failed"
        console.print(f"\n  [bold]KK test:[/bold] {status}  (score={kk.get('consistency_score', 0):.3f})")

    if output_files:
        from science_cli.core.manifest import emit_manifest
        from science_cli.core.project import get_current_project_path
        emit_manifest(
            output_dir=out_dir,
            command=f"plot {filepath}",
            source_files=[filepath],
            output_files=output_files,
            technique="ec-eis",
            parameters=flags,
            project=get_current_project_path().name if get_current_project_path() else "",
        )


def _overlay_eis(files: list, flags: dict) -> None:
    """Overlay EIS — Nyquist + Bode overlays."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from rich.console import Console

    from science_cli.cli.commands.plot import _get_results_dir
    from science_cli.core.data_loader import load_data_file
    from science_cli.core.session import get_active_theme
    from science_cli.plot.eis import plot_eis_bode, plot_eis_nyquist
    from science_cli.theme import apply_theme

    console = Console()
    apply_theme(get_active_theme())
    cycle = mpl.rcParams["axes.prop_cycle"]
    colors = [entry["color"] for entry in cycle]
    custom_labels = flags.get("label-name") or flags.get("labels", "")
    label_list = [s.strip() for s in custom_labels.split(",") if s.strip()] if custom_labels else []

    fig, axes = plt.subplots(1, 2, figsize=(7, 3.5))
    nyq_ax, bode_ax = axes

    for idx, fp in enumerate(files):
        try:
            df, info = load_data_file(fp, technique="ec-eis")
        except Exception:
            continue
        cols = list(df.columns)
        def _col(candidates):
            for c in candidates:
                if c in cols:
                    return c
            return ""
        freq_col = _col(["frequency", "Frequency (Hz)"])
        z_real_col = _col(["z_real", "Z' (Ω)", "Z'"])
        z_imag_col = _col(["z_imag", "-Z'' (Ω)", "-Z''"])
        mag_col = _col(["magnitude", "Z (Ω)"])
        phase_col = _col(["phase", "-Phase (°)", "Phase (°)"])
        if not freq_col or not z_real_col or not z_imag_col:
            continue
        z_real = df[z_real_col].values
        z_imag = df[z_imag_col].values
        mag = df[mag_col].values if mag_col else None
        phase = df[phase_col].values if phase_col else None
        freq = df[freq_col].values
        color = colors[idx % len(colors)]
        label = label_list[idx] if idx < len(label_list) else Path(fp).stem
        cf = dict(flags, color=color)
        plot_eis_nyquist(z_real, z_imag, flags=cf, label=label, ax=nyq_ax)
        if phase is not None and mag is not None:
            plot_eis_bode(freq, mag, phase, flags=cf)

    nyq_ax.legend(fontsize=6)
    fig.tight_layout()
    out_dir = _get_results_dir(files[0])
    out_name = flags.get("n") or flags.get("name", "eis_overlay.pdf")
    if not Path(out_name).suffix:
        out_name = str(Path(out_name)) + ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", mpl.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[bold green]✓[/bold green] EIS overlay saved: {save_path}")

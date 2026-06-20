"""Pulse endurance plotting — cycles vs resistance, with device-type variants.

Device-type dispatch:
    volatile-memristor:  R_decay vs cycle (single panel, log x)
    non-volatile-memristor: R_high / R_low vs cycle (2 panels, log x)
"""
from pathlib import Path

from science_cli.core.plot_config import resolve_plot_config


# ── Helpers ──────────────────────────────────────────────────────────

def _load_endurance_data(filepath: str, technique: str = "pulse-endurance"):
    from science_cli.core.data_loader import load_data_file
    return load_data_file(filepath, technique=technique)


def _resolve_columns(df, info):
    """Return (cycle, resistance, xlabel, ylabel) or (None,)*4 on failure."""
    import numpy as np

    def _find(col_names):
        for c in col_names:
            if c in df.columns:
                return c
        return None

    xcol = _find(["Time", "time", "Cycle", "cycle", "index"]) or (df.columns[0] if len(df.columns) > 0 else None)
    ycol = _find(["MeasResult2_value", "current", "Current", "I"]) or (df.columns[1] if len(df.columns) > 1 else None)
    if xcol is None or ycol is None:
        return None, None, None, None

    x, y = df[xcol].values, df[ycol].values
    try:
        cycle = np.arange(1, len(x) + 1, dtype=float) if len(x) > 1 and x.dtype.kind == "f" else x.astype(float)
    except (ValueError, TypeError):
        cycle = np.arange(1, len(x) + 1, dtype=float)

    vcol = _find(["MeasResult1_value", "voltage", "Voltage", "V"])
    if vcol is not None:
        try:
            v, i_arr = df[vcol].values.astype(float), y.astype(float)
            mask = np.abs(i_arr) > 1e-15
            r = np.full_like(i_arr, np.nan)
            r[mask] = np.abs(v[mask] / i_arr[mask])
        except (ValueError, TypeError):
            r = y.astype(float)
    else:
        r = y.astype(float)

    return cycle, r, "Cycle", "Resistance (Ω)"


def _save_fig(fig, filepath: str, flags: dict, suffix: str = "") -> None:
    import matplotlib as plt_mod
    from science_cli.cli.commands.plot import _get_results_dir
    out_dir = _get_results_dir(filepath)
    stem = Path(filepath).stem
    out_name = flags.get("n") or flags.get("name", f"endurance{suffix}_{stem}.pdf")
    if not Path(out_name).suffix:
        out_name += ".pdf"
    save_path = out_dir / out_name
    dpi = int(flags.get("dpi", plt_mod.rcParams.get("savefig.dpi", 600)))
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt_mod.pyplot.close(fig)
    from rich.console import Console
    Console().print(f"[bold green]✓[/bold green] Endurance saved: {save_path}")


def _load_and_resolve(filepath, console_msg: str):
    """Load data and resolve columns. Returns (df, info, cycle, r, xlabel, ylabel) or None."""
    from rich.console import Console
    try:
        df, info = _load_endurance_data(filepath)
    except Exception as e:
        Console().print(f"[red]Failed to load endurance data: {e}[/red]")
        return None
    cycle, r, xlabel, ylabel = _resolve_columns(df, info)
    if cycle is None:
        Console().print(f"[red]{console_msg}[/red]")
        return None
    return df, info, cycle, r, xlabel, ylabel


def _apply_common_style(ax, flags: dict, cycle, r, xlabel, ylabel,
                         label: str = "", plot_cfg: dict | None = None):
    """Apply endurance defaults: big markers, log x."""
    cfg = plot_cfg or {}
    marker = flags.get("marker", cfg.get("series.hrs.marker", "o"))
    markersize = float(flags.get("markersize", cfg.get("series.hrs.markersize", 4)))
    lw = float(flags.get("linewidth", cfg.get("series.hrs.linewidth", 1.0)))
    alpha = float(cfg.get("series.hrs.alpha", 0.85))
    kw = dict(marker=marker, markersize=markersize, linewidth=lw, alpha=alpha)
    if label:
        kw["label"] = label
    ax.plot(cycle, r, **kw)
    ax.set_xscale("log")
    ax.set_xlabel(flags.get("xlabel", xlabel))
    ax.set_ylabel(flags.get("ylabel", ylabel))


# ── Base plotter (generic / unknown device type) ────────────────────

def _plot_endurance(filepath: str, flags: dict) -> None:
    """Plot endurance cycling data: cycles vs resistance."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    plot_cfg = resolve_plot_config("pulse:pulse-endurance")

    data = _load_and_resolve(filepath, "Could not determine x/y columns for endurance.")
    if data is None:
        return
    _, _, cycle, r, xlabel, ylabel = data

    figsize = parse_figsize(flags) or tuple(plot_cfg.get("figure.figsize", [3.46, 2.75]))
    fig, ax = plt.subplots(figsize=figsize)
    _apply_common_style(ax, flags, cycle, r, xlabel, ylabel, plot_cfg=plot_cfg)
    apply_figure_kw(ax, flags, Path(filepath).stem)
    _save_fig(fig, filepath, flags)


# ── Volatile memristor: R_decay vs cycle ────────────────────────────

def _plot_endurance_volatile(filepath: str, flags: dict) -> None:
    """Volatile endurance — R_decay vs cycle (log x, log y, big markers)."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    plot_cfg = resolve_plot_config(
        "pulse:pulse-endurance", device_type="volatile-memristor",
    )

    data = _load_and_resolve(filepath, "Could not determine columns for volatile endurance.")
    if data is None:
        return
    _, _, cycle, r, xlabel, ylabel = data

    figsize = parse_figsize(flags) or tuple(plot_cfg.get("figure.figsize", [3.46, 2.75]))
    fig, ax = plt.subplots(figsize=figsize)
    color = flags.get("color", plot_cfg.get("series.hrs.color", "#2176AE"))
    label = plot_cfg.get("series.hrs.label", "R_decay")
    _apply_common_style(ax, flags, cycle, r, xlabel, ylabel, label=label, plot_cfg=plot_cfg)
    ax.lines[0].set_color(color)
    ax.set_yscale("log")
    ax.set_title("Volatile Memristor — Endurance")
    ax.legend()
    ax.grid(True, alpha=0.2)
    apply_figure_kw(ax, flags, Path(filepath).stem)
    _save_fig(fig, filepath, flags, suffix="_volatile")


# ── Non-volatile memristor: R_high / R_low vs cycle ────────────────

def _plot_endurance_nonvolatile(filepath: str, flags: dict) -> None:
    """NV endurance — 2 panels: R_high + R_low (log x, big markers)."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import parse_figsize
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    plot_cfg = resolve_plot_config(
        "pulse:pulse-endurance", device_type="non-volatile-memristor",
    )

    data = _load_and_resolve(filepath, "Could not determine columns for NV endurance.")
    if data is None:
        return
    _, _, cycle, r, xlabel, ylabel = data

    figsize_cfg = plot_cfg.get("figure.figsize", [3.46, 2.75])
    figsize = parse_figsize(flags) or (figsize_cfg[0] * 2, figsize_cfg[1])
    fig, (ax_hi, ax_lo) = plt.subplots(1, 2, figsize=figsize)
    hrs_marker = flags.get("marker", plot_cfg.get("series.hrs.marker", "o"))
    lrs_marker = flags.get("marker", plot_cfg.get("series.lrs.marker", "s"))
    hrs_markersize = float(flags.get("markersize", plot_cfg.get("series.hrs.markersize", 4)))
    lrs_markersize = float(flags.get("markersize", plot_cfg.get("series.lrs.markersize", 4)))
    hrs_lw = float(flags.get("linewidth", plot_cfg.get("series.hrs.linewidth", 1.0)))
    lrs_lw = float(flags.get("linewidth", plot_cfg.get("series.lrs.linewidth", 1.0)))
    hrs_alpha = float(plot_cfg.get("series.hrs.alpha", 0.85))
    lrs_alpha = float(plot_cfg.get("series.lrs.alpha", 0.85))

    # Split data: first half → R_high, second half → R_low
    # (actual separation comes from analyzer in Seq 4)
    r_clean = r[~np.isnan(r)] if np.issubdtype(r.dtype, np.floating) else r
    if len(r_clean) == 0:
        from rich.console import Console
        Console().print("[red]All resistance values are NaN.[/red]")
        return
    mid = max(len(r_clean) // 2, 1)
    r_hi, r_lo = r_clean[:mid], r_clean[mid:]
    cyc_hi = np.arange(1, len(r_hi) + 1, dtype=float)
    cyc_lo = np.arange(1, len(r_lo) + 1, dtype=float)

    color_hi = flags.get("color-hi", plot_cfg.get("series.hrs.color", "#CC0000"))
    color_lo = flags.get("color-lo", plot_cfg.get("series.lrs.color", "#0055CC"))
    xlbl = flags.get("xlabel", xlabel)

    for ax, cy, rv, cl, title, ylbl, mk, ms, lw, al in [
        (ax_hi, cyc_hi, r_hi, color_hi, "High Resistance State", "R_high (Ω)",
         hrs_marker, hrs_markersize, hrs_lw, hrs_alpha),
        (ax_lo, cyc_lo, r_lo, color_lo, "Low Resistance State", "R_low (Ω)",
         lrs_marker, lrs_markersize, lrs_lw, lrs_alpha),
    ]:
        ax.plot(cy, rv, marker=mk, markersize=ms, color=cl,
                linewidth=lw, alpha=al, label=title.split()[0] + " " + title.split()[-1])
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(xlbl)
        ax.set_ylabel(ylbl)
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.2)

    fig.suptitle("Non-Volatile Memristor — Endurance", fontsize=11)
    fig.tight_layout()
    _save_fig(fig, filepath, flags, suffix="_nv")


# Alias for backward compat
_plot_endurance_nv = _plot_endurance_nonvolatile


# ── Overlay functions ───────────────────────────────────────────────

def _overlay_generic_endurance(files: list, flags: dict) -> None:
    from science_cli.cli.commands.plot import _generic_overlay
    _generic_overlay(files, flags, technique="mem-endurance")


_overlay_endurance = _overlay_generic_endurance
_overlay_endurance_volatile = _overlay_generic_endurance
_overlay_endurance_nonvolatile = _overlay_generic_endurance

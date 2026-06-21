"""Pulse endurance plotting — cycles vs resistance, with device-type variants.

Device-type dispatch:
    volatile-memristor:  R_decay vs cycle (single panel, log x)
    non-volatile-memristor: R_high / R_low vs cycle (2 panels, log x)

Pre-processed format:
    When fed a CSV with columns (cycle, r_hrs_ohm, r_lrs_ohm, ratio),
    the functions plot directly from those columns (no R=V/I computation).
    This is the output of the pre-processing script (sci-keysight-endurance skill).
"""
from pathlib import Path

import pandas as pd

from science_cli.core.plot_config import resolve_plot_config


# ── Pre-processed format detection ───────────────────────────────────

def _load_preprocessed(filepath: str) -> tuple | None:
    """Detect and load pre-processed endurance CSV (cycle, r_hrs_ohm, r_lrs_ohm, ratio).

    Returns (cycle, r_hrs, r_lrs, ratio) or None if columns don't match.

    The new 9-column extracted-list format has a 2-line voltage header
    (V_LRS,<value> and V_HRS,<value>) before the CSV column names, so we
    must skip those 2 header rows.
    """
    try:
        df = pd.read_csv(filepath, skiprows=2)
    except Exception:
        return None
    cols = set(df.columns)
    if not {"cycle", "r_hrs_ohm", "r_lrs_ohm"}.issubset(cols):
        return None
    cycle = df["cycle"].values.astype(float)
    r_hrs = df["r_hrs_ohm"].values.astype(float)
    r_lrs = df["r_lrs_ohm"].values.astype(float)
    ratio = df["ratio"].values.astype(float) if "ratio" in cols else r_hrs / r_lrs
    return cycle, r_hrs, r_lrs, ratio


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
    """Plot endurance cycling data: cycles vs resistance (generic / unknown device)."""
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    plot_cfg = resolve_plot_config("pulse:pulse-endurance")

    # Try pre-processed format (3-panel: HRS + LRS + ratio)
    pp = _load_preprocessed(filepath)
    if pp is not None:
        cycle, r_hrs, r_lrs, ratio = pp
        figsize = parse_figsize(flags) or tuple(plot_cfg.get("figure.figsize", [3.46, 2.75]))
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(figsize[0] * 2, figsize[1] * 1.8),
                                        gridspec_kw={"height_ratios": [1.5, 1]})
        color_hrs = flags.get("color-hrs", plot_cfg.get("series.hrs.color", "#CC0000"))
        color_lrs = flags.get("color-lrs", plot_cfg.get("series.lrs.color", "#0055CC"))
        color_r = flags.get("color-ratio", plot_cfg.get("series.ratio.color", "#CC7700"))
        lw = float(flags.get("linewidth", plot_cfg.get("series.hrs.linewidth", 1.0)))
        ax1.plot(cycle, r_hrs, color=color_hrs, linewidth=lw, alpha=0.85, label="HRS")
        ax1.plot(cycle, r_lrs, color=color_lrs, linewidth=lw, alpha=0.85, label="LRS")
        ax1.set_xscale("log"); ax1.set_yscale("log")
        ax1.set_ylabel("Resistance (Ω)"); ax1.legend(); ax1.grid(True, alpha=0.2)
        ax2.plot(cycle, ratio, color=color_r, linewidth=lw, alpha=0.85)
        ax2.set_xscale("log"); ax2.set_yscale("log")
        ax2.set_xlabel("Cycle"); ax2.set_ylabel("HRS / LRS")
        fig.suptitle("Endurance", fontsize=11)
        fig.tight_layout()
        _save_fig(fig, filepath, flags)
        return

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
    """Volatile endurance — R_decay vs cycle (log x, log y, big markers).

    Detects pre-processed CSV format (cycle, r_hrs_ohm, r_lrs_ohm, ratio)
    and plots both HRS + LRS when available instead of single R_decay.
    """
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from science_cli.core.session import get_active_theme
    from science_cli.plot.base import apply_figure_kw, parse_figsize
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    plot_cfg = resolve_plot_config(
        "pulse:pulse-endurance", device_type="volatile-memristor",
    )

    # Try pre-processed format first
    pp = _load_preprocessed(filepath)
    if pp is not None:
        cycle, r_hrs, r_lrs, ratio = pp
        is_preprocessed = True
    else:
        data = _load_and_resolve(filepath, "Could not determine columns for volatile endurance.")
        if data is None:
            return
        _, _, cycle, r, xlabel, ylabel = data
        r_hrs, r_lrs, ratio = r, None, None
        is_preprocessed = False

    figsize = parse_figsize(flags) or tuple(plot_cfg.get("figure.figsize", [3.46, 2.75]))

    if is_preprocessed:
        # 2-panel: HRS + LRS (top), ratio (bottom)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(figsize[0] * 2, figsize[1] * 1.8),
                                        gridspec_kw={"height_ratios": [1.5, 1]})

        color_hrs = flags.get("color-hrs", plot_cfg.get("series.hrs.color", "#CC0000"))
        color_lrs = flags.get("color-lrs", plot_cfg.get("series.lrs.color", "#0055CC"))
        color_ratio = flags.get("color-ratio", plot_cfg.get("series.ratio.color", "#CC7700"))

        lw = float(flags.get("linewidth", plot_cfg.get("series.hrs.linewidth", 1.0)))

        ax1.plot(cycle, r_hrs, color=color_hrs, linewidth=lw, alpha=0.85, label="HRS")
        ax1.plot(cycle, r_lrs, color=color_lrs, linewidth=lw, alpha=0.85, label="LRS")
        ax1.set_xscale("log")
        ax1.set_yscale("log")
        ax1.set_ylabel("Resistance (Ω)")
        ax1.legend()
        ax1.grid(True, alpha=0.2)

        ax2.plot(cycle, ratio, color=color_ratio, linewidth=lw, alpha=0.85)
        ax2.set_xscale("log")
        ax2.set_yscale("log")
        ax2.set_xlabel("Cycle")
        ax2.set_ylabel("HRS / LRS")

        fig.suptitle("Volatile Memristor — Endurance", fontsize=11)
    else:
        # Legacy single-panel (R only)
        fig, ax = plt.subplots(figsize=figsize)
        color = flags.get("color", plot_cfg.get("series.hrs.color", "#2176AE"))
        label = plot_cfg.get("series.hrs.label", "R_decay")
        _apply_common_style(ax, flags, cycle, r_hrs, "Cycle", "Resistance (Ω)",
                             label=label, plot_cfg=plot_cfg)
        ax.lines[0].set_color(color)
        ax.set_yscale("log")
        ax.set_title("Volatile Memristor — Endurance")
        ax.legend()
        ax.grid(True, alpha=0.2)
        apply_figure_kw(ax, flags, Path(filepath).stem)

    fig.tight_layout()
    apply_figure_kw(ax if not is_preprocessed else fig.axes[0], flags, Path(filepath).stem)
    _save_fig(fig, filepath, flags, suffix="_volatile")


# ── Non-volatile memristor: R_high / R_low vs cycle ────────────────

def _plot_endurance_nonvolatile(filepath: str, flags: dict) -> None:
    """NV endurance — 2 panels: R_high + R_low (log x, big markers).

    Pre-processed format: plots HRS and LRS directly from columns.
    """
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

    # Try pre-processed format
    pp = _load_preprocessed(filepath)
    if pp is not None:
        cycle, r_hrs, r_lrs, ratio = pp
        figsize_cfg = plot_cfg.get("figure.figsize", [3.46, 2.75])
        figsize = parse_figsize(flags) or (figsize_cfg[0] * 2, figsize_cfg[1])
        fig, (ax_hi, ax_lo) = plt.subplots(1, 2, figsize=figsize)
        color_hi = flags.get("color-hi", plot_cfg.get("series.hrs.color", "#CC0000"))
        color_lo = flags.get("color-lo", plot_cfg.get("series.lrs.color", "#0055CC"))
        lw = float(flags.get("linewidth", plot_cfg.get("series.hrs.linewidth", 1.0)))
        for ax, cy, rv, cl, title, ylbl in [
            (ax_hi, cycle, r_hrs, color_hi, "High Resistance State", "R_high (Ω)"),
            (ax_lo, cycle, r_lrs, color_lo, "Low Resistance State", "R_low (Ω)"),
        ]:
            ax.plot(cy, rv, color=cl, linewidth=lw, alpha=0.85, label=title.split()[0])
            ax.set_xscale("log"); ax.set_yscale("log")
            ax.set_xlabel("Cycle"); ax.set_ylabel(ylbl); ax.set_title(title)
            ax.legend(); ax.grid(True, alpha=0.2)
        fig.suptitle("Non-Volatile Memristor — Endurance", fontsize=11)
        fig.tight_layout()
        _save_fig(fig, filepath, flags, suffix="_nv")
        return

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


# ── Menu-driven handlers (called by interactive_menu.dispatch) ──────

def _load_extracted_list(csv_path: Path) -> tuple | None:
    """Load extracted-list CSV with 2-line voltage header.

    Returns (df, v_set, v_read) or None on failure.
    The first line is V_LRS,<value>, second line is V_HRS,<value>,
    followed by the CSV column headers.
    """
    try:
        with open(csv_path) as f:
            line1 = f.readline().strip()
            line2 = f.readline().strip()
        v_set = float(line1.split(",")[1])
        v_read = float(line2.split(",")[1])
        df = pd.read_csv(csv_path, skiprows=2)
        return df, v_set, v_read
    except Exception:
        return None


def plot_resistance(file_path: Path = None, **kwargs) -> None:
    """Plot R_HRS, R_LRS, ratio vs cycles.

    Called by interactive_menu dispatch.
    Delegates to the existing _plot_endurance which handles
    the pre-processed 3-panel resistance plot.
    """
    _plot_endurance(str(file_path), {})


def plot_current(file_path: Path = None, **kwargs) -> None:
    """Plot I_LRS, I_HRS vs cycles.

    Loads extracted-list CSV, plots i_lrs_A and i_hrs_A columns
    as current vs cycle (log-log, single panel) with voltage annotations.
    """
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt

    from science_cli.core.session import get_active_theme
    from science_cli.theme import apply_theme
    apply_theme(get_active_theme())

    loaded = _load_extracted_list(file_path)
    if loaded is None:
        from rich.console import Console
        Console().print("[red]Failed to load extracted-list CSV for current plot.[/red]")
        return
    df, v_set, v_read = loaded

    fig, ax = plt.subplots(figsize=(3.46, 2.75))

    ax.plot(df["cycle"], df["i_lrs_A"], "o-", color="#0055CC",
            markersize=4, linewidth=1.0, alpha=0.8, label="I_LRS")
    ax.plot(df["cycle"], df["i_hrs_A"], "s-", color="#CC0000",
            markersize=4, linewidth=1.0, alpha=0.8, label="I_HRS")

    ax.set_xlabel("Cycle")
    ax.set_ylabel("Current (A)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(True, alpha=0.25)
    ax.legend()

    # Annotate voltages
    ax.annotate(f"V_set = {v_set:.2f}V", xy=(0.02, 0.98), xycoords="axes fraction",
                fontsize=8, va="top", color="#0055CC")
    ax.annotate(f"V_read = {v_read:.2f}V", xy=(0.02, 0.88), xycoords="axes fraction",
                fontsize=8, va="top", color="#CC0000")

    _save_fig(fig, str(file_path), {}, suffix="_current")


def plot_both(file_path: Path = None, **kwargs) -> None:
    """Plot both resistance and current as separate files."""
    plot_resistance(file_path=file_path, **kwargs)
    plot_current(file_path=file_path, **kwargs)
